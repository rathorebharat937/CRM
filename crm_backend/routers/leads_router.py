from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import STAFF_ROLES
from lead_config import LEAD_SOURCES, LEAD_STATUSES, normalize_phone
from models import Company, Contact, Lead, User
from services.workflow_events import emit_workflow_event
from schemas import (
    LeadConvertResponse,
    LeadCreateRequest,
    LeadDuplicateCheckResponse,
    LeadDuplicateMatch,
    LeadListResponse,
    LeadResponse,
    LeadStatsResponse,
    LeadUpdateRequest,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/leads", tags=["leads"])



def _get_lead(db: Session, lead_id: int, company_id: int) -> Lead:
    lead = (
        db.query(Lead)
        .options(
            joinedload(Lead.assigned_to),
            joinedload(Lead.created_by),
        )
        .filter(Lead.id == lead_id, Lead.company_id == company_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def _validate_status(status: str) -> None:
    if status not in LEAD_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(LEAD_STATUSES)}",
        )


def _validate_source(source: str) -> None:
    if source not in LEAD_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Source must be one of: {', '.join(LEAD_SOURCES)}",
        )


def _validate_assigned_to(db: Session, assigned_to_id: int | None, company_id: int):
    if assigned_to_id is None:
        return
    staff = (
        db.query(User)
        .filter(
            User.id == assigned_to_id,
            User.company_id == company_id,
            User.role.in_(STAFF_ROLES),
            User.status == "active",
        )
        .first()
    )
    if not staff:
        raise HTTPException(status_code=400, detail="Invalid assigned staff member")


def _lead_to_response(lead: Lead) -> LeadResponse:
    return LeadResponse(
        id=lead.id,
        company_id=lead.company_id,
        contact_id=lead.contact_id,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        organization_name=lead.organization_name,
        city=lead.city,
        requirement=lead.requirement,
        exact_requirement=lead.exact_requirement,
        source=lead.source,
        status=lead.status,
        csv_status=lead.csv_status,
        notes=lead.notes,
        assigned_to_id=lead.assigned_to_id,
        assigned_to_name=lead.assigned_to.name if lead.assigned_to else None,
        created_by_id=lead.created_by_id,
        created_by_name=lead.created_by.name if lead.created_by else None,
        registered_at=lead.registered_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def _phone_tail(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return digits or None


@router.get("/stats/summary", response_model=LeadStatsResponse)
def lead_stats(
    user: User = Depends(require_permission("leads.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    rows = (
        db.query(Lead.status, func.count(Lead.id))
        .filter(Lead.company_id == company.id)
        .group_by(Lead.status)
        .all()
    )
    counts = {status: 0 for status in LEAD_STATUSES}
    total = 0
    for status, count in rows:
        counts[status] = count
        total += count
    return LeadStatsResponse(total=total, **counts)


@router.get("/sources", response_model=list[str])
def list_lead_sources(_: User = Depends(require_permission("leads.view"))):
    return LEAD_SOURCES


@router.get("/statuses", response_model=list[str])
def list_lead_statuses(_: User = Depends(require_permission("leads.view"))):
    return LEAD_STATUSES


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def list_lead_assignees(
    user: User = Depends(require_permission("leads.assign")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    staff = (
        db.query(User)
        .filter(
            User.company_id == company.id,
            User.role.in_(["Admin", "Manager"]),
            User.status == "active",
        )
        .order_by(User.name)
        .all()
    )
    return [
        StaffAssigneeResponse(id=u.id, name=u.name, email=u.email, role=u.role)
        for u in staff
    ]


@router.get("/check-duplicate", response_model=LeadDuplicateCheckResponse)
def check_lead_duplicate(
    phone: str = Query(..., min_length=8),
    user: User = Depends(require_permission("leads.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    normalized = normalize_phone(phone)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    tail = _phone_tail(normalized)
    lead_query = db.query(Lead).filter(Lead.company_id == company.id)
    contact_query = db.query(Contact).filter(Contact.company_id == company.id)

    if tail:
        lead_matches = lead_query.filter(Lead.phone.like(f"%{tail}")).limit(5).all()
        contact_matches = contact_query.filter(Contact.phone.like(f"%{tail}")).limit(5).all()
    else:
        lead_matches = lead_query.filter(Lead.phone == normalized).limit(5).all()
        contact_matches = contact_query.filter(Contact.phone == normalized).limit(5).all()

    leads = [
        LeadDuplicateMatch(
            id=lead.id,
            name=lead.name,
            phone=lead.phone,
            organization_name=lead.organization_name,
        )
        for lead in lead_matches
    ]
    contacts = [
        LeadDuplicateMatch(
            id=contact.id,
            name=contact.name,
            phone=contact.phone,
            organization_name=contact.organization_name,
        )
        for contact in contact_matches
    ]
    return LeadDuplicateCheckResponse(
        phone=normalized,
        has_duplicates=bool(leads or contacts),
        leads=leads,
        contacts=contacts,
    )


@router.get("", response_model=LeadListResponse)
def list_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    source: str | None = None,
    assigned_to_id: int | None = None,
    search: str | None = None,
    user: User = Depends(require_permission("leads.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(Lead)
        .options(joinedload(Lead.assigned_to), joinedload(Lead.created_by))
        .filter(Lead.company_id == company.id)
    )

    if status:
        _validate_status(status)
        query = query.filter(Lead.status == status)
    if source:
        _validate_source(source)
        query = query.filter(Lead.source == source)
    if assigned_to_id is not None:
        query = query.filter(Lead.assigned_to_id == assigned_to_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Lead.name.ilike(term),
                Lead.organization_name.ilike(term),
                Lead.phone.ilike(term),
                Lead.email.ilike(term),
                Lead.exact_requirement.ilike(term),
            )
        )

    total = query.count()
    items = (
        query.order_by(Lead.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return LeadListResponse(
        items=[_lead_to_response(lead) for lead in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: int,
    user: User = Depends(require_permission("leads.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    return _lead_to_response(_get_lead(db, lead_id, company.id))


@router.post("", response_model=LeadResponse)
def create_lead(
    data: LeadCreateRequest,
    request: Request,
    user: User = Depends(require_permission("leads.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    payload = data.model_dump()
    _validate_status(payload["status"])
    _validate_source(payload["source"])
    _validate_assigned_to(db, payload.get("assigned_to_id"), company.id)

    phone = normalize_phone(payload.get("phone"))
    lead = Lead(
        company_id=company.id,
        created_by_id=user.id,
        name=payload["name"].strip(),
        phone=phone,
        email=(payload.get("email") or "").strip().lower() or None,
        organization_name=payload.get("organization_name"),
        city=payload.get("city"),
        requirement=payload.get("requirement"),
        exact_requirement=payload.get("exact_requirement"),
        source=payload["source"],
        status=payload["status"],
        notes=payload.get("notes"),
        assigned_to_id=payload.get("assigned_to_id"),
        registered_at=payload.get("registered_at") or datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    log_activity(
        db,
        "lead_created",
        user_id=user.id,
        email=user.email,
        details=f"Created lead {lead.name}",
        ip_address=get_client_ip(request),
    )
    emit_workflow_event(
        db,
        company_id=company.id,
        trigger_type="lead.created",
        record_type="lead",
        record_id=lead.id,
        actor_id=user.id,
    )
    return _lead_to_response(_get_lead(db, lead.id, company.id))


@router.put("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    data: LeadUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("leads.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    lead = _get_lead(db, lead_id, company.id)
    payload = data.model_dump()
    _validate_status(payload["status"])
    _validate_source(payload["source"])

    if payload.get("assigned_to_id") != lead.assigned_to_id:
        if not user.role in {"Admin", "Manager"}:
            raise HTTPException(
                status_code=403,
                detail="Only Admin or Manager can assign leads",
            )
    _validate_assigned_to(db, payload.get("assigned_to_id"), company.id)

    lead.name = payload["name"].strip()
    lead.phone = normalize_phone(payload.get("phone"))
    lead.email = (payload.get("email") or "").strip().lower() or None
    lead.organization_name = payload.get("organization_name")
    lead.city = payload.get("city")
    lead.requirement = payload.get("requirement")
    lead.exact_requirement = payload.get("exact_requirement")
    lead.source = payload["source"]
    lead.status = payload["status"]
    lead.notes = payload.get("notes")
    lead.assigned_to_id = payload.get("assigned_to_id")
    if payload.get("registered_at"):
        lead.registered_at = payload["registered_at"]

    db.commit()

    log_activity(
        db,
        "lead_updated",
        user_id=user.id,
        email=user.email,
        details=f"Updated lead {lead.name}",
        ip_address=get_client_ip(request),
    )
    return _lead_to_response(_get_lead(db, lead.id, company.id))


@router.post("/{lead_id}/convert-to-contact", response_model=LeadConvertResponse)
def convert_lead_to_contact(
    lead_id: int,
    request: Request,
    user: User = Depends(require_permission("leads.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    lead = _get_lead(db, lead_id, company.id)

    if lead.contact_id:
        raise HTTPException(status_code=400, detail="Lead already converted to a contact")

    contact = Contact(
        company_id=company.id,
        created_by_id=user.id,
        assigned_to_id=lead.assigned_to_id,
        name=lead.name,
        organization_name=lead.organization_name,
        email=lead.email,
        phone=lead.phone,
        contact_type="Customer",
        status="active",
        city=lead.city,
        country="India",
        designation=lead.requirement,
    )
    db.add(contact)
    db.flush()

    lead.contact_id = contact.id
    lead.status = "converted"
    db.commit()
    db.refresh(lead)

    log_activity(
        db,
        "lead_converted",
        user_id=user.id,
        email=user.email,
        details=f"Converted lead {lead.name} to contact #{contact.id}",
        ip_address=get_client_ip(request),
    )

    return LeadConvertResponse(
        lead=_lead_to_response(_get_lead(db, lead.id, company.id)),
        contact_id=contact.id,
        message="Lead converted to contact successfully",
    )
