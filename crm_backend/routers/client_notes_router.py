from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from client_note_config import (
    FOLLOW_UP_PRIORITIES,
    NOTE_TYPE_LABELS,
    NOTE_TYPES,
    VISIBILITY_LABELS,
    VISIBILITY_SCOPES,
)
from config import STAFF_ROLES
from models import (
    ClientNote,
    ClientNoteRevision,
    Company,
    Contact,
    Deal,
    Invoice,
    Lead,
    Quotation,
    SalesOrder,
    User,
)
from permissions import role_has_permission
from schemas import (
    ClientNoteCreateRequest,
    ClientNoteListResponse,
    ClientNoteResponse,
    ClientNoteRevisionResponse,
    ClientNoteStatsResponse,
    ClientNoteTypeOption,
    ClientNoteUpdateRequest,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/client-notes", tags=["client-notes"])




def _validate_note_type(note_type: str) -> None:
    if note_type not in NOTE_TYPES:
        raise HTTPException(status_code=400, detail=f"Note type must be one of: {', '.join(NOTE_TYPES)}")


def _validate_visibility(scope: str) -> None:
    if scope not in VISIBILITY_SCOPES:
        raise HTTPException(status_code=400, detail=f"Visibility must be one of: {', '.join(VISIBILITY_SCOPES)}")


def _validate_priority(priority: str) -> None:
    if priority not in FOLLOW_UP_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Priority must be one of: {', '.join(FOLLOW_UP_PRIORITIES)}")


def _can_view_sensitive(user: User, db: Session) -> bool:
    return role_has_permission(db, user.role, "client_notes.view_sensitive")


def _follow_up_overdue(note: ClientNote) -> bool:
    if not note.follow_up_required or note.follow_up_completed_at or not note.follow_up_due_date:
        return False
    return note.follow_up_due_date < datetime.now(timezone.utc)


def _note_resp(note: ClientNote, include_revisions: bool = False) -> ClientNoteResponse:
    return ClientNoteResponse(
        id=note.id,
        contact_id=note.contact_id,
        contact_name=note.contact.name if note.contact else None,
        lead_id=note.lead_id,
        deal_id=note.deal_id,
        deal_title=note.deal.title if note.deal else None,
        quotation_id=note.quotation_id,
        quotation_number=note.quotation.quote_number if note.quotation else None,
        sales_order_id=note.sales_order_id,
        sales_order_number=note.sales_order.order_number if note.sales_order else None,
        invoice_id=note.invoice_id,
        invoice_number=note.invoice.invoice_number if note.invoice else None,
        author_id=note.author_id,
        author_name=note.author.name if note.author else None,
        assigned_to_id=note.assigned_to_id,
        assigned_to_name=note.assigned_to.name if note.assigned_to else None,
        last_edited_by_id=note.last_edited_by_id,
        last_edited_by_name=note.last_edited_by.name if note.last_edited_by else None,
        note_type=note.note_type,
        title=note.title,
        body=note.body,
        visibility_scope=note.visibility_scope,
        tags=note.tags,
        structured_data=note.structured_data,
        is_pinned=note.is_pinned,
        pin_order=note.pin_order,
        is_sensitive=note.is_sensitive,
        is_resolved=note.is_resolved,
        follow_up_required=note.follow_up_required,
        follow_up_due_date=note.follow_up_due_date,
        follow_up_priority=note.follow_up_priority,
        follow_up_completed_at=note.follow_up_completed_at,
        follow_up_overdue=_follow_up_overdue(note),
        revision_count=note.revision_count,
        created_at=note.created_at,
        updated_at=note.updated_at,
        revisions=[
            ClientNoteRevisionResponse(
                id=r.id,
                editor_id=r.editor_id,
                editor_name=r.editor.name if r.editor else None,
                note_type=r.note_type,
                title=r.title,
                body=r.body,
                created_at=r.created_at,
            )
            for r in (note.revisions if include_revisions else [])
        ],
    )


def _get_note(db: Session, note_id: int, company_id: int) -> ClientNote:
    note = (
        db.query(ClientNote)
        .options(
            joinedload(ClientNote.author),
            joinedload(ClientNote.assigned_to),
            joinedload(ClientNote.last_edited_by),
            joinedload(ClientNote.contact),
            joinedload(ClientNote.deal),
            joinedload(ClientNote.quotation),
            joinedload(ClientNote.sales_order),
            joinedload(ClientNote.invoice),
            joinedload(ClientNote.revisions).joinedload(ClientNoteRevision.editor),
        )
        .filter(ClientNote.id == note_id, ClientNote.company_id == company_id, ClientNote.is_deleted.is_(False))
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Client note not found")
    return note


def _apply_visibility_filter(query, user: User, db: Session):
    if not _can_view_sensitive(user, db):
        query = query.filter(
            ClientNote.is_sensitive.is_(False),
            ClientNote.visibility_scope != "sensitive",
        )
    return query


def _resolve_contact_id(db: Session, company_id: int, payload: ClientNoteCreateRequest) -> int | None:
    if payload.contact_id:
        contact = db.query(Contact).filter(Contact.id == payload.contact_id, Contact.company_id == company_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        return contact.id
    if payload.lead_id:
        lead = db.query(Lead).filter(Lead.id == payload.lead_id, Lead.company_id == company_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead.contact_id
    if payload.deal_id:
        deal = db.query(Deal).filter(Deal.id == payload.deal_id, Deal.company_id == company_id).first()
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")
        return deal.contact_id
    if payload.quotation_id:
        quote = db.query(Quotation).filter(Quotation.id == payload.quotation_id, Quotation.company_id == company_id).first()
        if not quote:
            raise HTTPException(status_code=404, detail="Quotation not found")
        return quote.contact_id
    if payload.sales_order_id:
        order = db.query(SalesOrder).filter(SalesOrder.id == payload.sales_order_id, SalesOrder.company_id == company_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Sales order not found")
        return order.contact_id
    if payload.invoice_id:
        inv = db.query(Invoice).filter(Invoice.id == payload.invoice_id, Invoice.company_id == company_id).first()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return inv.contact_id
    return None


def _can_edit_note(note: ClientNote, user: User, db: Session) -> bool:
    if role_has_permission(db, user.role, "client_notes.edit_all"):
        return True
    if role_has_permission(db, user.role, "client_notes.edit_own") and note.author_id == user.id:
        return True
    return False


@router.get("/types", response_model=list[ClientNoteTypeOption])
def note_types(_: User = Depends(require_permission("client_notes.view"))):
    return [ClientNoteTypeOption(value=t, label=NOTE_TYPE_LABELS[t]) for t in NOTE_TYPES]


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def assignees(_: User = Depends(require_permission("client_notes.view")), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.role.in_(STAFF_ROLES), User.status == "active").order_by(User.name).all()
    return [StaffAssigneeResponse(id=u.id, name=u.name, email=u.email, role=u.role) for u in users]


@router.get("/stats/summary", response_model=ClientNoteStatsResponse)
def stats(user: User = Depends(require_permission("client_notes.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    base = db.query(ClientNote).filter(ClientNote.company_id == company.id, ClientNote.is_deleted.is_(False))
    base = _apply_visibility_filter(base, user, db)
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    return ClientNoteStatsResponse(
        total=base.count(),
        pinned=base.filter(ClientNote.is_pinned.is_(True)).count(),
        follow_up_pending=base.filter(
            ClientNote.follow_up_required.is_(True),
            ClientNote.follow_up_completed_at.is_(None),
        ).count(),
        follow_up_overdue=base.filter(
            ClientNote.follow_up_required.is_(True),
            ClientNote.follow_up_completed_at.is_(None),
            ClientNote.follow_up_due_date < now,
        ).count(),
        recent_7_days=base.filter(ClientNote.created_at >= week_ago).count(),
    )


@router.get("/follow-up-queue", response_model=ClientNoteListResponse)
def follow_up_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("client_notes.manage_followups")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(ClientNote)
        .options(
            joinedload(ClientNote.author),
            joinedload(ClientNote.assigned_to),
            joinedload(ClientNote.contact),
            joinedload(ClientNote.deal),
            joinedload(ClientNote.quotation),
            joinedload(ClientNote.sales_order),
            joinedload(ClientNote.invoice),
        )
        .filter(
            ClientNote.company_id == company.id,
            ClientNote.is_deleted.is_(False),
            ClientNote.follow_up_required.is_(True),
            ClientNote.follow_up_completed_at.is_(None),
        )
    )
    query = _apply_visibility_filter(query, user, db)
    total = query.count()
    notes = (
        query.order_by(ClientNote.follow_up_due_date.asc().nullslast(), ClientNote.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ClientNoteListResponse(
        items=[_note_resp(n) for n in notes],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("", response_model=ClientNoteListResponse)
def list_notes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    contact_id: int | None = None,
    lead_id: int | None = None,
    deal_id: int | None = None,
    quotation_id: int | None = None,
    sales_order_id: int | None = None,
    invoice_id: int | None = None,
    note_type: str | None = None,
    author_id: int | None = None,
    tag: str | None = None,
    pinned: bool | None = None,
    follow_up_required: bool | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user: User = Depends(require_permission("client_notes.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(ClientNote)
        .options(
            joinedload(ClientNote.author),
            joinedload(ClientNote.assigned_to),
            joinedload(ClientNote.last_edited_by),
            joinedload(ClientNote.contact),
            joinedload(ClientNote.deal),
            joinedload(ClientNote.quotation),
            joinedload(ClientNote.sales_order),
            joinedload(ClientNote.invoice),
        )
        .filter(ClientNote.company_id == company.id, ClientNote.is_deleted.is_(False))
    )
    query = _apply_visibility_filter(query, user, db)

    if contact_id:
        query = query.filter(ClientNote.contact_id == contact_id)
    if lead_id:
        query = query.filter(ClientNote.lead_id == lead_id)
    if deal_id:
        query = query.filter(ClientNote.deal_id == deal_id)
    if quotation_id:
        query = query.filter(ClientNote.quotation_id == quotation_id)
    if sales_order_id:
        query = query.filter(ClientNote.sales_order_id == sales_order_id)
    if invoice_id:
        query = query.filter(ClientNote.invoice_id == invoice_id)
    if note_type:
        _validate_note_type(note_type)
        query = query.filter(ClientNote.note_type == note_type)
    if author_id:
        query = query.filter(ClientNote.author_id == author_id)
    if tag:
        query = query.filter(ClientNote.tags.ilike(f"%{tag.strip()}%"))
    if pinned is not None:
        query = query.filter(ClientNote.is_pinned.is_(pinned))
    if follow_up_required is not None:
        query = query.filter(ClientNote.follow_up_required.is_(follow_up_required))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(ClientNote.title.ilike(term), ClientNote.body.ilike(term), ClientNote.tags.ilike(term)))
    if date_from:
        query = query.filter(ClientNote.created_at >= date_from)
    if date_to:
        query = query.filter(ClientNote.created_at <= date_to)

    total = query.count()
    notes = (
        query.order_by(ClientNote.is_pinned.desc(), ClientNote.pin_order.desc(), ClientNote.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ClientNoteListResponse(items=[_note_resp(n) for n in notes], total=total, page=page, limit=limit)


@router.post("", response_model=ClientNoteResponse, status_code=201)
def create_note(
    payload: ClientNoteCreateRequest,
    request: Request,
    user: User = Depends(require_permission("client_notes.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    _validate_note_type(payload.note_type)
    _validate_visibility(payload.visibility_scope)
    _validate_priority(payload.follow_up_priority)

    if not any([payload.contact_id, payload.lead_id, payload.deal_id, payload.quotation_id, payload.sales_order_id, payload.invoice_id]):
        raise HTTPException(status_code=400, detail="Note must be linked to a contact or CRM record")

    contact_id = _resolve_contact_id(db, company.id, payload)
    if payload.is_sensitive or payload.visibility_scope == "sensitive":
        if not _can_view_sensitive(user, db):
            raise HTTPException(status_code=403, detail="Not allowed to create sensitive notes")

    pin_order = 0
    if payload.is_pinned:
        max_pin = db.query(func.max(ClientNote.pin_order)).filter(
            ClientNote.company_id == company.id, ClientNote.is_pinned.is_(True)
        ).scalar() or 0
        pin_order = max_pin + 1

    note = ClientNote(
        company_id=company.id,
        contact_id=contact_id,
        lead_id=payload.lead_id,
        deal_id=payload.deal_id,
        quotation_id=payload.quotation_id,
        sales_order_id=payload.sales_order_id,
        invoice_id=payload.invoice_id,
        author_id=user.id,
        assigned_to_id=payload.assigned_to_id or user.id,
        note_type=payload.note_type,
        title=payload.title.strip(),
        body=payload.body.strip(),
        visibility_scope=payload.visibility_scope,
        tags=payload.tags.strip() if payload.tags else None,
        structured_data=payload.structured_data,
        is_pinned=payload.is_pinned,
        pin_order=pin_order,
        is_sensitive=payload.is_sensitive or payload.visibility_scope == "sensitive",
        follow_up_required=payload.follow_up_required,
        follow_up_due_date=payload.follow_up_due_date,
        follow_up_priority=payload.follow_up_priority,
    )
    db.add(note)
    db.commit()
    note = _get_note(db, note.id, company.id)

    log_activity(
        db,
        "client_note_created",
        user_id=user.id,
        email=user.email,
        details=f"Client note: {note.title}",
        ip_address=get_client_ip(request),
    )
    return _note_resp(note)


@router.get("/{note_id}", response_model=ClientNoteResponse)
def get_note(
    note_id: int,
    user: User = Depends(require_permission("client_notes.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    note = _get_note(db, note_id, company.id)
    if note.is_sensitive and not _can_view_sensitive(user, db):
        raise HTTPException(status_code=403, detail="Not allowed to view sensitive note")
    return _note_resp(note, include_revisions=True)


@router.put("/{note_id}", response_model=ClientNoteResponse)
def update_note(
    note_id: int,
    payload: ClientNoteUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("client_notes.edit_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    note = _get_note(db, note_id, company.id)
    if not _can_edit_note(note, user, db):
        raise HTTPException(status_code=403, detail="Not allowed to edit this note")

    if payload.note_type:
        _validate_note_type(payload.note_type)
    if payload.visibility_scope:
        _validate_visibility(payload.visibility_scope)
    if payload.follow_up_priority:
        _validate_priority(payload.follow_up_priority)

    revision = ClientNoteRevision(
        client_note_id=note.id,
        editor_id=user.id,
        note_type=note.note_type,
        title=note.title,
        body=note.body,
    )
    db.add(revision)
    note.revision_count += 1
    note.last_edited_by_id = user.id

    if payload.note_type is not None:
        note.note_type = payload.note_type
    if payload.title is not None:
        note.title = payload.title.strip()
    if payload.body is not None:
        note.body = payload.body.strip()
    if payload.visibility_scope is not None:
        note.visibility_scope = payload.visibility_scope
    if payload.tags is not None:
        note.tags = payload.tags.strip() or None
    if payload.structured_data is not None:
        note.structured_data = payload.structured_data
    if payload.is_sensitive is not None:
        note.is_sensitive = payload.is_sensitive
    if payload.is_resolved is not None:
        note.is_resolved = payload.is_resolved
    if payload.follow_up_required is not None:
        note.follow_up_required = payload.follow_up_required
    if payload.follow_up_due_date is not None:
        note.follow_up_due_date = payload.follow_up_due_date
    if payload.follow_up_priority is not None:
        note.follow_up_priority = payload.follow_up_priority
    if payload.assigned_to_id is not None:
        note.assigned_to_id = payload.assigned_to_id
    if payload.is_pinned is not None:
        if payload.is_pinned and not note.is_pinned:
            max_pin = db.query(func.max(ClientNote.pin_order)).filter(
                ClientNote.company_id == company.id, ClientNote.is_pinned.is_(True)
            ).scalar() or 0
            note.pin_order = max_pin + 1
        note.is_pinned = payload.is_pinned
        if not payload.is_pinned:
            note.pin_order = 0

    if note.visibility_scope == "sensitive":
        note.is_sensitive = True

    db.commit()
    note = _get_note(db, note.id, company.id)
    log_activity(
        db,
        "client_note_edited",
        user_id=user.id,
        email=user.email,
        details=f"Edited note: {note.title}",
        ip_address=get_client_ip(request),
    )
    return _note_resp(note)


@router.delete("/{note_id}")
def delete_note(
    note_id: int,
    request: Request,
    user: User = Depends(require_permission("client_notes.delete")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    note = _get_note(db, note_id, company.id)
    note.is_deleted = True
    db.commit()
    log_activity(
        db,
        "client_note_deleted",
        user_id=user.id,
        email=user.email,
        details=f"Deleted note: {note.title}",
        ip_address=get_client_ip(request),
    )
    return {"ok": True}


@router.post("/{note_id}/pin", response_model=ClientNoteResponse)
def pin_note(
    note_id: int,
    request: Request,
    user: User = Depends(require_permission("client_notes.pin")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    note = _get_note(db, note_id, company.id)
    if not note.is_pinned:
        max_pin = db.query(func.max(ClientNote.pin_order)).filter(
            ClientNote.company_id == company.id, ClientNote.is_pinned.is_(True)
        ).scalar() or 0
        note.pin_order = max_pin + 1
    note.is_pinned = True
    db.commit()
    note = _get_note(db, note.id, company.id)
    log_activity(db, "client_note_pinned", user_id=user.id, email=user.email, details=note.title, ip_address=get_client_ip(request))
    return _note_resp(note)


@router.post("/{note_id}/unpin", response_model=ClientNoteResponse)
def unpin_note(
    note_id: int,
    user: User = Depends(require_permission("client_notes.pin")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    note = _get_note(db, note_id, company.id)
    note.is_pinned = False
    note.pin_order = 0
    db.commit()
    return _note_resp(_get_note(db, note.id, company.id))


@router.post("/{note_id}/complete-followup", response_model=ClientNoteResponse)
def complete_followup(
    note_id: int,
    request: Request,
    user: User = Depends(require_permission("client_notes.manage_followups")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    note = _get_note(db, note_id, company.id)
    note.follow_up_completed_at = datetime.now(timezone.utc)
    note.is_resolved = True
    db.commit()
    note = _get_note(db, note.id, company.id)
    log_activity(db, "client_note_followup_completed", user_id=user.id, email=user.email, details=note.title, ip_address=get_client_ip(request))
    return _note_resp(note)
