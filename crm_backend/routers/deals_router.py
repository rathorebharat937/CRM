from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import STAFF_ROLES
from deal_config import (
    CLOSED_DEAL_STAGES,
    DEAL_STAGE_LABELS,
    DEAL_STAGES,
    PIPELINE_STAGES,
)
from models import Company, Contact, Deal, Lead, Product, User
from schemas import (
    DealCreateRequest,
    DealListResponse,
    DealPipelineColumn,
    DealPipelineResponse,
    DealResponse,
    DealStageUpdateRequest,
    DealStatsResponse,
    DealUpdateRequest,
    StaffAssigneeResponse,
)
from services.workflow_events import emit_deal_lifecycle, emit_workflow_event

router = APIRouter(prefix="/deals", tags=["deals"])



def _validate_stage(stage: str) -> None:
    if stage not in DEAL_STAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Stage must be one of: {', '.join(DEAL_STAGES)}",
        )


def _get_deal(db: Session, deal_id: int, company_id: int) -> Deal:
    deal = (
        db.query(Deal)
        .options(
            joinedload(Deal.assigned_to),
            joinedload(Deal.created_by),
            joinedload(Deal.lead),
            joinedload(Deal.contact),
            joinedload(Deal.product),
        )
        .filter(Deal.id == deal_id, Deal.company_id == company_id)
        .first()
    )
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


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


def _validate_lead(db: Session, lead_id: int | None, company_id: int):
    if lead_id is None:
        return
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.company_id == company_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=400, detail="Invalid lead")


def _validate_contact(db: Session, contact_id: int | None, company_id: int):
    if contact_id is None:
        return
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.company_id == company_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=400, detail="Invalid contact")


def _validate_product(db: Session, product_id: int | None, company_id: int):
    if product_id is None:
        return
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == company_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=400, detail="Invalid product")


def _deal_to_response(deal: Deal) -> DealResponse:
    return DealResponse(
        id=deal.id,
        company_id=deal.company_id,
        title=deal.title,
        stage=deal.stage,
        expected_value=float(deal.expected_value) if deal.expected_value is not None else None,
        currency=deal.currency,
        expected_close_date=deal.expected_close_date,
        notes=deal.notes,
        lost_reason=deal.lost_reason,
        closed_at=deal.closed_at,
        lead_id=deal.lead_id,
        lead_name=deal.lead.name if deal.lead else None,
        contact_id=deal.contact_id,
        contact_name=deal.contact.name if deal.contact else None,
        product_id=deal.product_id,
        product_name=deal.product.name if deal.product else None,
        assigned_to_id=deal.assigned_to_id,
        assigned_to_name=deal.assigned_to.name if deal.assigned_to else None,
        created_by_id=deal.created_by_id,
        created_by_name=deal.created_by.name if deal.created_by else None,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
    )


def _apply_closed_stage(deal: Deal, stage: str, lost_reason: str | None = None) -> None:
    if stage in CLOSED_DEAL_STAGES:
        if deal.closed_at is None:
            deal.closed_at = datetime.now(timezone.utc)
        if stage == "lost":
            deal.lost_reason = lost_reason
        else:
            deal.lost_reason = None
    else:
        deal.closed_at = None
        deal.lost_reason = None


def _build_deal_from_payload(
    db: Session,
    company: Company,
    payload: dict,
    user: User,
) -> Deal:
    _validate_stage(payload["stage"])
    _validate_assigned_to(db, payload.get("assigned_to_id"), company.id)
    _validate_lead(db, payload.get("lead_id"), company.id)
    _validate_contact(db, payload.get("contact_id"), company.id)
    _validate_product(db, payload.get("product_id"), company.id)

    deal = Deal(
        company_id=company.id,
        created_by_id=user.id,
        title=payload["title"].strip(),
        stage=payload["stage"],
        expected_value=payload.get("expected_value"),
        currency=payload.get("currency") or company.currency or "INR",
        expected_close_date=payload.get("expected_close_date"),
        notes=payload.get("notes"),
        lead_id=payload.get("lead_id"),
        contact_id=payload.get("contact_id"),
        product_id=payload.get("product_id"),
        assigned_to_id=payload.get("assigned_to_id"),
    )
    _apply_closed_stage(deal, deal.stage, payload.get("lost_reason"))
    return deal


@router.get("/stats/summary", response_model=DealStatsResponse)
def deal_stats(
    user: User = Depends(require_permission("deals.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    rows = (
        db.query(Deal.stage, func.count(Deal.id))
        .filter(Deal.company_id == company.id)
        .group_by(Deal.stage)
        .all()
    )
    counts = {stage: 0 for stage in DEAL_STAGES}
    total = 0
    for stage, count in rows:
        counts[stage] = count
        total += count

    pipeline_value = (
        db.query(func.coalesce(func.sum(Deal.expected_value), 0))
        .filter(
            Deal.company_id == company.id,
            Deal.stage.in_(PIPELINE_STAGES),
        )
        .scalar()
    )
    won_value = (
        db.query(func.coalesce(func.sum(Deal.expected_value), 0))
        .filter(Deal.company_id == company.id, Deal.stage == "won")
        .scalar()
    )

    return DealStatsResponse(
        total=total,
        new=counts["new"],
        contacted=counts["contacted"],
        meeting=counts["meeting"],
        proposal=counts["proposal"],
        won=counts["won"],
        lost=counts["lost"],
        pipeline_value=float(pipeline_value or 0),
        won_value=float(won_value or 0),
    )


@router.get("/stages", response_model=list[dict])
def list_deal_stages(_: User = Depends(require_permission("deals.view"))):
    return [
        {"value": stage, "label": DEAL_STAGE_LABELS[stage]}
        for stage in DEAL_STAGES
    ]


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def list_deal_assignees(
    user: User = Depends(require_permission("deals.assign")),
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


@router.get("/pipeline", response_model=DealPipelineResponse)
def pipeline_board(
    assigned_to_id: int | None = None,
    search: str | None = None,
    include_closed: bool = Query(False),
    closed_limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("deals.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    base_query = (
        db.query(Deal)
        .options(
            joinedload(Deal.assigned_to),
            joinedload(Deal.created_by),
            joinedload(Deal.lead),
            joinedload(Deal.contact),
            joinedload(Deal.product),
        )
        .filter(Deal.company_id == company.id)
    )

    if assigned_to_id is not None:
        base_query = base_query.filter(Deal.assigned_to_id == assigned_to_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        base_query = base_query.filter(
            or_(
                Deal.title.ilike(term),
                Deal.notes.ilike(term),
            )
        )

    columns: list[DealPipelineColumn] = []
    for stage in PIPELINE_STAGES:
        stage_deals = (
            base_query.filter(Deal.stage == stage)
            .order_by(Deal.updated_at.desc())
            .all()
        )
        total_value = sum(
            float(d.expected_value or 0) for d in stage_deals
        )
        columns.append(
            DealPipelineColumn(
                stage=stage,
                label=DEAL_STAGE_LABELS[stage],
                count=len(stage_deals),
                total_value=total_value,
                deals=[_deal_to_response(d) for d in stage_deals],
            )
        )

    closed: list[DealResponse] = []
    if include_closed:
        closed_deals = (
            base_query.filter(Deal.stage.in_(CLOSED_DEAL_STAGES))
            .order_by(Deal.closed_at.desc().nullslast(), Deal.updated_at.desc())
            .limit(closed_limit)
            .all()
        )
        closed = [_deal_to_response(d) for d in closed_deals]

    return DealPipelineResponse(columns=columns, closed=closed)


@router.get("", response_model=DealListResponse)
def list_deals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    stage: str | None = None,
    assigned_to_id: int | None = None,
    search: str | None = None,
    user: User = Depends(require_permission("deals.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(Deal)
        .options(
            joinedload(Deal.assigned_to),
            joinedload(Deal.created_by),
            joinedload(Deal.lead),
            joinedload(Deal.contact),
            joinedload(Deal.product),
        )
        .filter(Deal.company_id == company.id)
    )

    if stage:
        _validate_stage(stage)
        query = query.filter(Deal.stage == stage)
    if assigned_to_id is not None:
        query = query.filter(Deal.assigned_to_id == assigned_to_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Deal.title.ilike(term),
                Deal.notes.ilike(term),
            )
        )

    total = query.count()
    items = (
        query.order_by(Deal.updated_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return DealListResponse(
        items=[_deal_to_response(deal) for deal in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{deal_id}", response_model=DealResponse)
def get_deal(
    deal_id: int,
    user: User = Depends(require_permission("deals.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    return _deal_to_response(_get_deal(db, deal_id, company.id))


@router.post("", response_model=DealResponse)
def create_deal(
    data: DealCreateRequest,
    request: Request,
    user: User = Depends(require_permission("deals.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    payload = data.model_dump()
    if payload.get("lost_reason") and payload["stage"] != "lost":
        payload["lost_reason"] = None

    deal = _build_deal_from_payload(db, company, payload, user)
    db.add(deal)
    db.commit()
    db.refresh(deal)

    log_activity(
        db,
        "deal_created",
        user_id=user.id,
        email=user.email,
        details=f"Created deal {deal.title}",
        ip_address=get_client_ip(request),
    )
    emit_workflow_event(
        db,
        company_id=company.id,
        trigger_type="deal.created",
        record_type="deal",
        record_id=deal.id,
        actor_id=user.id,
    )
    return _deal_to_response(_get_deal(db, deal.id, company.id))


@router.put("/{deal_id}", response_model=DealResponse)
def update_deal(
    deal_id: int,
    data: DealUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("deals.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    deal = _get_deal(db, deal_id, company.id)
    payload = data.model_dump()
    _validate_stage(payload["stage"])
    _validate_assigned_to(db, payload.get("assigned_to_id"), company.id)
    _validate_lead(db, payload.get("lead_id"), company.id)
    _validate_contact(db, payload.get("contact_id"), company.id)
    _validate_product(db, payload.get("product_id"), company.id)

    if payload.get("assigned_to_id") != deal.assigned_to_id:
        if user.role not in {"Admin", "Manager"}:
            raise HTTPException(
                status_code=403,
                detail="Only Admin or Manager can assign deals",
            )

    old_stage = deal.stage
    deal.title = payload["title"].strip()
    deal.stage = payload["stage"]
    deal.expected_value = payload.get("expected_value")
    deal.currency = payload.get("currency") or deal.currency
    deal.expected_close_date = payload.get("expected_close_date")
    deal.notes = payload.get("notes")
    deal.lead_id = payload.get("lead_id")
    deal.contact_id = payload.get("contact_id")
    deal.product_id = payload.get("product_id")
    deal.assigned_to_id = payload.get("assigned_to_id")
    _apply_closed_stage(deal, deal.stage, payload.get("lost_reason"))

    db.commit()

    details = f"Updated deal {deal.title}"
    if old_stage != deal.stage:
        details = f"Moved deal {deal.title} from {old_stage} to {deal.stage}"

    log_activity(
        db,
        "deal_updated" if old_stage == deal.stage else "deal_stage_changed",
        user_id=user.id,
        email=user.email,
        details=details,
        ip_address=get_client_ip(request),
    )
    emit_deal_lifecycle(
        db,
        company_id=company.id,
        deal_id=deal.id,
        old_stage=old_stage,
        new_stage=deal.stage,
        actor_id=user.id,
    )
    return _deal_to_response(_get_deal(db, deal.id, company.id))


@router.patch("/{deal_id}/stage", response_model=DealResponse)
def update_deal_stage(
    deal_id: int,
    data: DealStageUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("deals.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    deal = _get_deal(db, deal_id, company.id)
    _validate_stage(data.stage)

    if data.stage == "lost" and not (data.lost_reason or deal.lost_reason):
        raise HTTPException(
            status_code=400,
            detail="Lost reason is required when marking a deal as lost",
        )

    old_stage = deal.stage
    deal.stage = data.stage
    _apply_closed_stage(deal, deal.stage, data.lost_reason)
    db.commit()

    log_activity(
        db,
        "deal_stage_changed",
        user_id=user.id,
        email=user.email,
        details=f"Moved deal {deal.title} from {old_stage} to {deal.stage}",
        ip_address=get_client_ip(request),
    )
    emit_deal_lifecycle(
        db,
        company_id=company.id,
        deal_id=deal.id,
        old_stage=old_stage,
        new_stage=deal.stage,
        actor_id=user.id,
    )
    return _deal_to_response(_get_deal(db, deal.id, company.id))


@router.post("/from-lead/{lead_id}", response_model=DealResponse)
def create_deal_from_lead(
    lead_id: int,
    request: Request,
    user: User = Depends(require_permission("deals.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    lead = _get_lead(db, lead_id, company.id)

    title = lead.organization_name or lead.name
    if lead.requirement:
        title = f"{title} — {lead.requirement}"

    existing = (
        db.query(Deal)
        .filter(
            Deal.company_id == company.id,
            Deal.lead_id == lead.id,
            Deal.stage.in_(PIPELINE_STAGES),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Lead already has an open deal (#{existing.id})",
        )

    deal = Deal(
        company_id=company.id,
        lead_id=lead.id,
        created_by_id=user.id,
        assigned_to_id=lead.assigned_to_id,
        title=title[:200],
        stage="new",
        notes=lead.exact_requirement or lead.notes,
        currency=company.currency or "INR",
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)

    log_activity(
        db,
        "deal_created",
        user_id=user.id,
        email=user.email,
        details=f"Created deal from lead {lead.name}",
        ip_address=get_client_ip(request),
    )
    return _deal_to_response(_get_deal(db, deal.id, company.id))


@router.post("/from-contact/{contact_id}", response_model=DealResponse)
def create_deal_from_contact(
    contact_id: int,
    request: Request,
    user: User = Depends(require_permission("deals.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.company_id == company.id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    title = contact.organization_name or contact.name
    deal = Deal(
        company_id=company.id,
        contact_id=contact.id,
        created_by_id=user.id,
        assigned_to_id=contact.assigned_to_id,
        title=title[:200],
        stage="new",
        currency=company.currency or "INR",
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)

    log_activity(
        db,
        "deal_created",
        user_id=user.id,
        email=user.email,
        details=f"Created deal from contact {contact.name}",
        ip_address=get_client_ip(request),
    )
    return _deal_to_response(_get_deal(db, deal.id, company.id))


def _get_lead(db: Session, lead_id: int, company_id: int) -> Lead:
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.company_id == company_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
