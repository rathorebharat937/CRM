from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from auth_utils import get_client_ip, get_db, require_permission
from services.notification_service import create_notification
from config import STAFF_ROLES
from models import Company, Contact, ContactActivity, ContactNote, User
from schemas import (
    ContactActivityCreateRequest,
    ContactActivityResponse,
    ContactCreateRequest,
    ContactListResponse,
    ContactNoteCreateRequest,
    ContactNoteResponse,
    ContactResponse,
    ContactStatsResponse,
    ContactUpdateRequest,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/contacts", tags=["contacts"])

CONTACT_TYPES = {"Customer", "Vendor", "Partner", "Other"}
ACTIVITY_TYPES = {"note", "call", "email", "meeting"}

GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


def _validate_tax_ids(gstin: str | None, pan: str | None) -> None:
    if gstin and not GSTIN_PATTERN.match(gstin.upper()):
        raise HTTPException(status_code=400, detail="Invalid GSTIN format")
    if pan and not PAN_PATTERN.match(pan.upper()):
        raise HTTPException(status_code=400, detail="Invalid PAN format")


def _normalize_tax(data: dict) -> dict:
    if data.get("gstin"):
        data["gstin"] = data["gstin"].upper()
    if data.get("pan"):
        data["pan"] = data["pan"].upper()
    return data


def _get_company(db: Session) -> Company:
    company = db.query(Company).first()
    if not company:
        raise HTTPException(
            status_code=400,
            detail="Company must be configured before managing contacts",
        )
    return company


def _get_contact(db: Session, contact_id: int, company_id: int) -> Contact:
    contact = (
        db.query(Contact)
        .options(
            joinedload(Contact.assigned_to),
            joinedload(Contact.created_by),
        )
        .filter(Contact.id == contact_id, Contact.company_id == company_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


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


def _contact_to_response(contact: Contact) -> ContactResponse:
    return ContactResponse(
        id=contact.id,
        company_id=contact.company_id,
        user_id=contact.user_id,
        name=contact.name,
        organization_name=contact.organization_name,
        email=contact.email,
        phone=contact.phone,
        alt_phone=contact.alt_phone,
        contact_type=contact.contact_type,
        status=contact.status,
        designation=contact.designation,
        website=contact.website,
        address_line1=contact.address_line1,
        address_line2=contact.address_line2,
        city=contact.city,
        state=contact.state,
        pincode=contact.pincode,
        country=contact.country,
        gstin=contact.gstin,
        pan=contact.pan,
        assigned_to_id=contact.assigned_to_id,
        assigned_to_name=contact.assigned_to.name if contact.assigned_to else None,
        created_by_id=contact.created_by_id,
        created_by_name=contact.created_by.name if contact.created_by else None,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


@router.get("/stats/summary", response_model=ContactStatsResponse)
def contact_stats(
    _: User = Depends(require_permission("contacts.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    total = (
        db.query(func.count(Contact.id))
        .filter(Contact.company_id == company.id)
        .scalar()
        or 0
    )
    active = (
        db.query(func.count(Contact.id))
        .filter(Contact.company_id == company.id, Contact.status == "active")
        .scalar()
        or 0
    )
    inactive = total - active
    active_pct = round((active / total) * 100, 1) if total else 0
    inactive_pct = round((inactive / total) * 100, 1) if total else 0
    return ContactStatsResponse(
        total=total,
        active=active,
        inactive=inactive,
        active_percent=active_pct,
        inactive_percent=inactive_pct,
    )


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def list_assignees(
    _: User = Depends(require_permission("contacts.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    staff = (
        db.query(User)
        .filter(
            User.company_id == company.id,
            User.role.in_(STAFF_ROLES),
            User.status == "active",
        )
        .order_by(User.name)
        .all()
    )
    return [
        StaffAssigneeResponse(id=u.id, name=u.name, email=u.email, role=u.role)
        for u in staff
    ]


@router.get("", response_model=ContactListResponse)
def list_contacts(
    search: str | None = None,
    contact_type: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("contacts.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    query = (
        db.query(Contact)
        .options(joinedload(Contact.assigned_to))
        .filter(Contact.company_id == company.id)
    )

    if status:
        query = query.filter(Contact.status == status)
    if contact_type:
        if contact_type not in CONTACT_TYPES:
            raise HTTPException(status_code=400, detail="Invalid contact type")
        query = query.filter(Contact.contact_type == contact_type)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Contact.name.ilike(term),
                Contact.organization_name.ilike(term),
                Contact.email.ilike(term),
                Contact.phone.ilike(term),
            )
        )

    total = query.count()
    contacts = (
        query.order_by(Contact.updated_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return ContactListResponse(
        items=[_contact_to_response(c) for c in contacts],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: int,
    _: User = Depends(require_permission("contacts.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    return _contact_to_response(_get_contact(db, contact_id, company.id))


@router.post("", response_model=ContactResponse)
def create_contact(
    data: ContactCreateRequest,
    request: Request,
    user: User = Depends(require_permission("contacts.create")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)

    if data.contact_type not in CONTACT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid contact type")

    payload = _normalize_tax(data.model_dump())
    _validate_tax_ids(payload.get("gstin"), payload.get("pan"))
    _validate_assigned_to(db, payload.get("assigned_to_id"), company.id)

    contact = Contact(
        company_id=company.id,
        created_by_id=user.id,
        **payload,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    contact = _get_contact(db, contact.id, company.id)

    log_activity(
        db,
        "contact_created",
        user_id=user.id,
        email=user.email,
        details=f"Created contact {contact.name} ({contact.contact_type})",
        ip_address=get_client_ip(request),
    )

    create_notification(db, "Contact Created", f"A new contact {contact.name} was created.", "SUCCESS")

    return _contact_to_response(contact)


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    data: ContactUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("contacts.edit")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    contact = _get_contact(db, contact_id, company.id)

    if data.contact_type not in CONTACT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid contact type")
    if data.status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="Status must be active or inactive")

    payload = _normalize_tax(data.model_dump())
    _validate_tax_ids(payload.get("gstin"), payload.get("pan"))
    _validate_assigned_to(db, payload.get("assigned_to_id"), company.id)

    old_status = contact.status
    for key, value in payload.items():
        setattr(contact, key, value)

    db.commit()
    contact = _get_contact(db, contact_id, company.id)

    details = f"Updated contact {contact.name}"
    if payload["status"] != old_status:
        details = f"Changed {contact.name} status to {contact.status}"

    log_activity(
        db,
        "contact_updated",
        user_id=user.id,
        email=user.email,
        details=details,
        ip_address=get_client_ip(request),
    )

    return _contact_to_response(contact)


@router.get("/{contact_id}/notes", response_model=list[ContactNoteResponse])
def list_notes(
    contact_id: int,
    _: User = Depends(require_permission("contacts.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    _get_contact(db, contact_id, company.id)
    notes = (
        db.query(ContactNote)
        .options(joinedload(ContactNote.author))
        .filter(ContactNote.contact_id == contact_id)
        .order_by(ContactNote.created_at.desc())
        .all()
    )
    return [
        ContactNoteResponse(
            id=n.id,
            contact_id=n.contact_id,
            body=n.body,
            author_id=n.author_id,
            author_name=n.author.name if n.author else None,
            created_at=n.created_at,
        )
        for n in notes
    ]


@router.post("/{contact_id}/notes", response_model=ContactNoteResponse)
def add_note(
    contact_id: int,
    data: ContactNoteCreateRequest,
    request: Request,
    user: User = Depends(require_permission("contacts.edit")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    contact = _get_contact(db, contact_id, company.id)

    note = ContactNote(
        contact_id=contact.id,
        author_id=user.id,
        body=data.body.strip(),
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    log_activity(
        db,
        "contact_note_added",
        user_id=user.id,
        email=user.email,
        details=f"Note added on {contact.name}",
        ip_address=get_client_ip(request),
    )

    return ContactNoteResponse(
        id=note.id,
        contact_id=note.contact_id,
        body=note.body,
        author_id=note.author_id,
        author_name=user.name,
        created_at=note.created_at,
    )


@router.get("/{contact_id}/activities", response_model=list[ContactActivityResponse])
def list_activities(
    contact_id: int,
    _: User = Depends(require_permission("contacts.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    _get_contact(db, contact_id, company.id)
    activities = (
        db.query(ContactActivity)
        .options(joinedload(ContactActivity.author))
        .filter(ContactActivity.contact_id == contact_id)
        .order_by(ContactActivity.created_at.desc())
        .all()
    )
    return [
        ContactActivityResponse(
            id=a.id,
            contact_id=a.contact_id,
            activity_type=a.activity_type,
            subject=a.subject,
            body=a.body,
            author_id=a.author_id,
            author_name=a.author.name if a.author else None,
            created_at=a.created_at,
        )
        for a in activities
    ]


@router.post("/{contact_id}/activities", response_model=ContactActivityResponse)
def add_activity(
    contact_id: int,
    data: ContactActivityCreateRequest,
    request: Request,
    user: User = Depends(require_permission("contacts.edit")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    contact = _get_contact(db, contact_id, company.id)

    if data.activity_type not in ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid activity type")

    activity = ContactActivity(
        contact_id=contact.id,
        author_id=user.id,
        activity_type=data.activity_type,
        subject=data.subject,
        body=data.body.strip(),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    log_activity(
        db,
        "contact_activity_added",
        user_id=user.id,
        email=user.email,
        details=f"{data.activity_type} logged on {contact.name}",
        ip_address=get_client_ip(request),
    )

    return ContactActivityResponse(
        id=activity.id,
        contact_id=activity.contact_id,
        activity_type=activity.activity_type,
        subject=activity.subject,
        body=activity.body,
        author_id=activity.author_id,
        author_name=user.name,
        created_at=activity.created_at,
    )
