from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import STAFF_ROLES
from models import ClientNote, Company, Contact, Deal, FollowUpReminder, Lead, User
from reminder_config import (
    REMINDER_PRIORITIES,
    REMINDER_STATUSES,
    REMINDER_TYPE_LABELS,
    REMINDER_TYPES,
)
from schemas import (
    FollowUpReminderCreateRequest,
    FollowUpReminderListResponse,
    FollowUpReminderResponse,
    FollowUpReminderStatsResponse,
    FollowUpReminderUpdateRequest,
    UnifiedFollowUpItem,
    UnifiedFollowUpQueueResponse,
)

router = APIRouter(prefix="/reminders", tags=["reminders"])




def _validate_type(reminder_type: str) -> None:
    if reminder_type not in REMINDER_TYPES:
        raise HTTPException(status_code=400, detail=f"Type must be one of: {', '.join(REMINDER_TYPES)}")


def _validate_priority(priority: str) -> None:
    if priority not in REMINDER_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Priority must be one of: {', '.join(REMINDER_PRIORITIES)}")


def _validate_status(status: str) -> None:
    if status not in REMINDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(REMINDER_STATUSES)}")


def _validate_links(db: Session, company_id: int, lead_id, deal_id, contact_id) -> None:
    if lead_id:
        if not db.query(Lead).filter(Lead.id == lead_id, Lead.company_id == company_id).first():
            raise HTTPException(status_code=400, detail="Invalid lead")
    if deal_id:
        if not db.query(Deal).filter(Deal.id == deal_id, Deal.company_id == company_id).first():
            raise HTTPException(status_code=400, detail="Invalid deal")
    if contact_id:
        if not db.query(Contact).filter(Contact.id == contact_id, Contact.company_id == company_id).first():
            raise HTTPException(status_code=400, detail="Invalid contact")
    if not any([lead_id, deal_id, contact_id]):
        raise HTTPException(status_code=400, detail="Link to a lead, deal, or contact is required")


def _is_overdue(due_at: datetime | None, *, status: str = "pending") -> bool:
    if not due_at or status != "pending":
        return False
    now = datetime.now(timezone.utc)
    due = due_at if due_at.tzinfo else due_at.replace(tzinfo=timezone.utc)
    return due < now


def _is_due_today(due_at: datetime | None, *, status: str = "pending") -> bool:
    if not due_at or status != "pending":
        return False
    now = datetime.now(timezone.utc)
    due = due_at if due_at.tzinfo else due_at.replace(tzinfo=timezone.utc)
    return due.date() == now.date()


def _day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _reminder_response(reminder: FollowUpReminder) -> FollowUpReminderResponse:
    entity_label = None
    entity_path = None
    if reminder.lead_id:
        entity_label = reminder.lead.name if reminder.lead else f"Lead #{reminder.lead_id}"
        entity_path = f"/leads/{reminder.lead_id}"
    elif reminder.deal_id:
        entity_label = reminder.deal.title if reminder.deal else f"Deal #{reminder.deal_id}"
        entity_path = f"/deals/{reminder.deal_id}"
    elif reminder.contact_id:
        entity_label = reminder.contact.name if reminder.contact else f"Contact #{reminder.contact_id}"
        entity_path = f"/contacts/{reminder.contact_id}"

    return FollowUpReminderResponse(
        id=reminder.id,
        company_id=reminder.company_id,
        lead_id=reminder.lead_id,
        deal_id=reminder.deal_id,
        contact_id=reminder.contact_id,
        entity_label=entity_label,
        entity_path=entity_path,
        reminder_type=reminder.reminder_type,
        reminder_type_label=REMINDER_TYPE_LABELS.get(reminder.reminder_type, reminder.reminder_type),
        title=reminder.title,
        notes=reminder.notes,
        status=reminder.status,
        priority=reminder.priority,
        due_at=reminder.due_at,
        completed_at=reminder.completed_at,
        assigned_to_id=reminder.assigned_to_id,
        assigned_to_name=reminder.assigned_to.name if reminder.assigned_to else None,
        created_by_id=reminder.created_by_id,
        created_by_name=reminder.created_by.name if reminder.created_by else None,
        is_overdue=_is_overdue(reminder.due_at, status=reminder.status),
        is_due_today=_is_due_today(reminder.due_at, status=reminder.status),
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
    )


def _get_reminder(db: Session, reminder_id: int, company_id: int) -> FollowUpReminder:
    reminder = (
        db.query(FollowUpReminder)
        .options(
            joinedload(FollowUpReminder.assigned_to),
            joinedload(FollowUpReminder.created_by),
            joinedload(FollowUpReminder.lead),
            joinedload(FollowUpReminder.deal),
            joinedload(FollowUpReminder.contact),
        )
        .filter(FollowUpReminder.id == reminder_id, FollowUpReminder.company_id == company_id)
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.get("/types", response_model=list[dict])
def list_reminder_types(_: User = Depends(require_permission("reminders.view"))):
    return [{"value": t, "label": REMINDER_TYPE_LABELS[t]} for t in REMINDER_TYPES]


@router.get("/stats/summary", response_model=FollowUpReminderStatsResponse)
def reminder_stats(
    assigned_to_id: int | None = None,
    user: User = Depends(require_permission("reminders.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    now = datetime.now(timezone.utc)
    start_of_day, end_of_day = _day_bounds(now)

    base = db.query(FollowUpReminder).filter(
        FollowUpReminder.company_id == company.id,
        FollowUpReminder.status == "pending",
    )
    if assigned_to_id is not None:
        base = base.filter(FollowUpReminder.assigned_to_id == assigned_to_id)

    due_today = base.filter(
        FollowUpReminder.due_at >= start_of_day,
        FollowUpReminder.due_at < end_of_day,
    ).count()
    overdue = base.filter(FollowUpReminder.due_at < now).count()
    upcoming = base.filter(FollowUpReminder.due_at >= end_of_day).count()
    total_pending = base.count()

    note_base = db.query(ClientNote).filter(
        ClientNote.company_id == company.id,
        ClientNote.is_deleted.is_(False),
        ClientNote.follow_up_required.is_(True),
        ClientNote.follow_up_completed_at.is_(None),
    )
    if assigned_to_id is not None:
        note_base = note_base.filter(ClientNote.assigned_to_id == assigned_to_id)

    note_overdue = note_base.filter(ClientNote.follow_up_due_date < now).count()
    note_due_today = note_base.filter(
        ClientNote.follow_up_due_date >= start_of_day,
        ClientNote.follow_up_due_date < end_of_day,
    ).count()

    return FollowUpReminderStatsResponse(
        total_pending=total_pending + note_base.count(),
        due_today=due_today + note_due_today,
        overdue=overdue + note_overdue,
        upcoming=upcoming + note_base.filter(ClientNote.follow_up_due_date >= end_of_day).count(),
        note_follow_ups_pending=note_base.count(),
    )


@router.get("/queue/unified", response_model=UnifiedFollowUpQueueResponse)
def unified_queue(
    filter: str = Query("all", pattern="^(all|due_today|overdue|upcoming)$"),
    assigned_to_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(require_permission("reminders.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    now = datetime.now(timezone.utc)
    start_of_day, end_of_day = _day_bounds(now)

    r_query = (
        db.query(FollowUpReminder)
        .options(
            joinedload(FollowUpReminder.assigned_to),
            joinedload(FollowUpReminder.lead),
            joinedload(FollowUpReminder.deal),
            joinedload(FollowUpReminder.contact),
        )
        .filter(
            FollowUpReminder.company_id == company.id,
            FollowUpReminder.status == "pending",
        )
    )
    if assigned_to_id is not None:
        r_query = r_query.filter(FollowUpReminder.assigned_to_id == assigned_to_id)

    if filter == "due_today":
        r_query = r_query.filter(
            FollowUpReminder.due_at >= start_of_day,
            FollowUpReminder.due_at < end_of_day,
        )
    elif filter == "overdue":
        r_query = r_query.filter(FollowUpReminder.due_at < now)
    elif filter == "upcoming":
        r_query = r_query.filter(FollowUpReminder.due_at >= end_of_day)

    reminders = r_query.order_by(FollowUpReminder.due_at.asc()).limit(limit).all()

    n_query = (
        db.query(ClientNote)
        .options(
            joinedload(ClientNote.assigned_to),
            joinedload(ClientNote.contact),
            joinedload(ClientNote.lead),
            joinedload(ClientNote.deal),
        )
        .filter(
            ClientNote.company_id == company.id,
            ClientNote.is_deleted.is_(False),
            ClientNote.follow_up_required.is_(True),
            ClientNote.follow_up_completed_at.is_(None),
        )
    )
    if assigned_to_id is not None:
        n_query = n_query.filter(ClientNote.assigned_to_id == assigned_to_id)
    if filter == "due_today":
        n_query = n_query.filter(
            ClientNote.follow_up_due_date >= start_of_day,
            ClientNote.follow_up_due_date < end_of_day,
        )
    elif filter == "overdue":
        n_query = n_query.filter(ClientNote.follow_up_due_date < now)
    elif filter == "upcoming":
        n_query = n_query.filter(ClientNote.follow_up_due_date >= end_of_day)

    notes = n_query.order_by(ClientNote.follow_up_due_date.asc().nullslast()).limit(limit).all()

    items: list[UnifiedFollowUpItem] = []
    for r in reminders:
        resp = _reminder_response(r)
        items.append(
            UnifiedFollowUpItem(
                source="reminder",
                id=r.id,
                title=r.title,
                subtitle=resp.entity_label,
                entity_path=resp.entity_path,
                reminder_type=resp.reminder_type_label,
                priority=r.priority,
                due_at=r.due_at,
                assigned_to_name=resp.assigned_to_name,
                is_overdue=resp.is_overdue,
                is_due_today=resp.is_due_today,
            )
        )

    for n in notes:
        entity_label = n.contact.name if n.contact else (n.deal.title if n.deal else (n.lead.name if n.lead else "—"))
        entity_path = None
        if n.lead_id:
            entity_path = f"/leads/{n.lead_id}"
        elif n.deal_id:
            entity_path = f"/deals/{n.deal_id}"
        elif n.contact_id:
            entity_path = f"/contacts/{n.contact_id}"

        due = n.follow_up_due_date
        items.append(
            UnifiedFollowUpItem(
                source="client_note",
                id=n.id,
                title=n.title,
                subtitle=entity_label,
                entity_path=entity_path,
                reminder_type="Client note",
                priority=n.follow_up_priority,
                due_at=due,
                assigned_to_name=n.assigned_to.name if n.assigned_to else None,
                is_overdue=_is_overdue(due),
                is_due_today=_is_due_today(due),
            )
        )

    items.sort(key=lambda x: (x.due_at is None, x.due_at or datetime.max.replace(tzinfo=timezone.utc)))
    return UnifiedFollowUpQueueResponse(items=items[:limit], total=len(items))


@router.get("", response_model=FollowUpReminderListResponse)
def list_reminders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = "pending",
    lead_id: int | None = None,
    deal_id: int | None = None,
    contact_id: int | None = None,
    assigned_to_id: int | None = None,
    user: User = Depends(require_permission("reminders.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(FollowUpReminder)
        .options(
            joinedload(FollowUpReminder.assigned_to),
            joinedload(FollowUpReminder.created_by),
            joinedload(FollowUpReminder.lead),
            joinedload(FollowUpReminder.deal),
            joinedload(FollowUpReminder.contact),
        )
        .filter(FollowUpReminder.company_id == company.id)
    )
    if status:
        _validate_status(status)
        query = query.filter(FollowUpReminder.status == status)
    if lead_id:
        query = query.filter(FollowUpReminder.lead_id == lead_id)
    if deal_id:
        query = query.filter(FollowUpReminder.deal_id == deal_id)
    if contact_id:
        query = query.filter(FollowUpReminder.contact_id == contact_id)
    if assigned_to_id is not None:
        query = query.filter(FollowUpReminder.assigned_to_id == assigned_to_id)

    total = query.count()
    items = (
        query.order_by(FollowUpReminder.due_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return FollowUpReminderListResponse(
        items=[_reminder_response(r) for r in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=FollowUpReminderResponse)
def create_reminder(
    data: FollowUpReminderCreateRequest,
    request: Request,
    user: User = Depends(require_permission("reminders.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    payload = data.model_dump()
    _validate_type(payload["reminder_type"])
    _validate_priority(payload["priority"])
    _validate_links(db, company.id, payload.get("lead_id"), payload.get("deal_id"), payload.get("contact_id"))

    assigned_to_id = payload.get("assigned_to_id") or user.id
    staff = (
        db.query(User)
        .filter(User.id == assigned_to_id, User.company_id == company.id, User.role.in_(STAFF_ROLES))
        .first()
    )
    if not staff:
        raise HTTPException(status_code=400, detail="Invalid assignee")

    reminder = FollowUpReminder(
        company_id=company.id,
        created_by_id=user.id,
        assigned_to_id=assigned_to_id,
        lead_id=payload.get("lead_id"),
        deal_id=payload.get("deal_id"),
        contact_id=payload.get("contact_id"),
        reminder_type=payload["reminder_type"],
        title=payload["title"].strip(),
        notes=payload.get("notes"),
        priority=payload["priority"],
        due_at=payload["due_at"],
        status="pending",
    )
    db.add(reminder)
    db.commit()

    log_activity(
        db,
        "reminder_created",
        user_id=user.id,
        email=user.email,
        details=f"Created reminder: {reminder.title}",
        ip_address=get_client_ip(request),
    )
    return _reminder_response(_get_reminder(db, reminder.id, company.id))


@router.patch("/{reminder_id}/complete", response_model=FollowUpReminderResponse)
def complete_reminder(
    reminder_id: int,
    request: Request,
    user: User = Depends(require_permission("reminders.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    reminder = _get_reminder(db, reminder_id, company.id)
    if reminder.status != "pending":
        raise HTTPException(status_code=400, detail="Reminder is not pending")

    reminder.status = "completed"
    reminder.completed_at = datetime.now(timezone.utc)
    db.commit()

    log_activity(
        db,
        "reminder_completed",
        user_id=user.id,
        email=user.email,
        details=f"Completed reminder: {reminder.title}",
        ip_address=get_client_ip(request),
    )
    return _reminder_response(_get_reminder(db, reminder.id, company.id))


@router.put("/{reminder_id}", response_model=FollowUpReminderResponse)
def update_reminder(
    reminder_id: int,
    data: FollowUpReminderUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("reminders.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    reminder = _get_reminder(db, reminder_id, company.id)
    payload = data.model_dump()
    _validate_type(payload["reminder_type"])
    _validate_priority(payload["priority"])
    _validate_status(payload["status"])
    _validate_links(db, company.id, payload.get("lead_id"), payload.get("deal_id"), payload.get("contact_id"))

    reminder.title = payload["title"].strip()
    reminder.notes = payload.get("notes")
    reminder.reminder_type = payload["reminder_type"]
    reminder.priority = payload["priority"]
    reminder.due_at = payload["due_at"]
    reminder.lead_id = payload.get("lead_id")
    reminder.deal_id = payload.get("deal_id")
    reminder.contact_id = payload.get("contact_id")
    reminder.assigned_to_id = payload.get("assigned_to_id") or reminder.assigned_to_id
    if payload["status"] == "completed" and reminder.status != "completed":
        reminder.completed_at = datetime.now(timezone.utc)
    reminder.status = payload["status"]

    db.commit()
    log_activity(
        db,
        "reminder_updated",
        user_id=user.id,
        email=user.email,
        details=f"Updated reminder: {reminder.title}",
        ip_address=get_client_ip(request),
    )
    return _reminder_response(_get_reminder(db, reminder.id, company.id))
