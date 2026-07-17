from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import Company, Contact, Project, ProjectTask, TimesheetEntry, User
from permissions import role_has_permission
from schemas import (
    TimesheetCreateRequest,
    TimesheetExportLogRequest,
    TimesheetListResponse,
    TimesheetMetaResponse,
    TimesheetOption,
    TimesheetRejectRequest,
    TimesheetResponse,
    TimesheetReviewRequest,
    TimesheetStatsResponse,
    TimesheetUpdateRequest,
)
from timesheet_config import (
    ALLOWED_TRANSITIONS,
    EDITABLE_STATUSES,
    MAX_HOURS,
    MIN_DESCRIPTION_LENGTH,
    MIN_HOURS,
    TIMESHEET_STATUS_LABELS,
    TIMESHEET_STATUSES,
)

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _week_start() -> datetime:
    now = _utcnow()
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)




def _float(v) -> float:
    return 0.0 if v is None else float(v)


def _date_only(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.replace(hour=12, minute=0, second=0, microsecond=0)


def _validate_status(status: str) -> None:
    if status not in TIMESHEET_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(TIMESHEET_STATUSES)}")


def _validate_hours(hours: float) -> None:
    if hours < MIN_HOURS or hours > MAX_HOURS:
        raise HTTPException(status_code=400, detail=f"Hours must be between {MIN_HOURS} and {MAX_HOURS}")


def _validate_description(description: str) -> None:
    text = (description or "").strip()
    if len(text) < MIN_DESCRIPTION_LENGTH:
        raise HTTPException(status_code=400, detail=f"Description must be at least {MIN_DESCRIPTION_LENGTH} characters")


def _transition(entry: TimesheetEntry, new_status: str) -> None:
    _validate_status(new_status)
    allowed = ALLOWED_TRANSITIONS.get(entry.status, set())
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {entry.status} to {new_status}")
    entry.status = new_status


def _generate_entry_number(db: Session, company: Company) -> str:
    year = _utcnow().year
    prefix = f"TS-{year}-"
    last = (
        db.query(TimesheetEntry)
        .filter(TimesheetEntry.company_id == company.id, TimesheetEntry.entry_number.like(f"{prefix}%"))
        .order_by(TimesheetEntry.id.desc())
        .first()
    )
    seq = 1
    if last and last.entry_number:
        try:
            seq = int(last.entry_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _user_has_view_all(user: User, db: Session) -> bool:
    return role_has_permission(db, user.role, "timesheets.view_all")


def _get_entry(db: Session, entry_id: int, company_id: int) -> TimesheetEntry:
    entry = (
        db.query(TimesheetEntry)
        .options(
            joinedload(TimesheetEntry.employee),
            joinedload(TimesheetEntry.project),
            joinedload(TimesheetEntry.task),
            joinedload(TimesheetEntry.contact),
            joinedload(TimesheetEntry.reviewed_by),
        )
        .filter(TimesheetEntry.id == entry_id, TimesheetEntry.company_id == company_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Timesheet entry not found")
    return entry


def _ensure_access(db: Session, user: User, entry: TimesheetEntry) -> None:
    if _user_has_view_all(user, db):
        return
    if entry.employee_id == user.id:
        return
    raise HTTPException(status_code=403, detail="You do not have access to this timesheet entry")


def _validate_project_task(db: Session, company_id: int, project_id: int | None, task_id: int | None) -> tuple[int | None, int | None, int | None]:
    contact_id = None
    if task_id is not None:
        task = (
            db.query(ProjectTask)
            .join(Project)
            .filter(ProjectTask.id == task_id, Project.company_id == company_id)
            .first()
        )
        if not task:
            raise HTTPException(status_code=400, detail="Invalid task")
        project_id = task.project_id
    if project_id is not None:
        project = db.query(Project).filter(Project.id == project_id, Project.company_id == company_id).first()
        if not project:
            raise HTTPException(status_code=400, detail="Invalid project")
        contact_id = project.contact_id
    return project_id, task_id, contact_id


def _entry_resp(entry: TimesheetEntry) -> TimesheetResponse:
    return TimesheetResponse(
        id=entry.id,
        entry_number=entry.entry_number,
        employee_id=entry.employee_id,
        employee_name=entry.employee.name if entry.employee else None,
        project_id=entry.project_id,
        project_name=entry.project.name if entry.project else None,
        project_number=entry.project.project_number if entry.project else None,
        task_id=entry.task_id,
        task_title=entry.task.title if entry.task else None,
        contact_id=entry.contact_id,
        contact_name=entry.contact.name if entry.contact else None,
        work_date=entry.work_date,
        hours=_float(entry.hours),
        is_billable=bool(entry.is_billable),
        description=entry.description,
        status=entry.status,
        status_label=TIMESHEET_STATUS_LABELS.get(entry.status, entry.status),
        submitted_at=entry.submitted_at,
        reviewed_by_id=entry.reviewed_by_id,
        reviewed_by_name=entry.reviewed_by.name if entry.reviewed_by else None,
        reviewed_at=entry.reviewed_at,
        reviewer_note=entry.reviewer_note,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/meta", response_model=TimesheetMetaResponse)
def timesheet_meta(
    current_user: User = Depends(require_permission("timesheets.view")),
):
    return TimesheetMetaResponse(
        statuses=[TimesheetOption(value=s, label=TIMESHEET_STATUS_LABELS[s]) for s in TIMESHEET_STATUSES],
    )


@router.get("/stats/summary", response_model=TimesheetStatsResponse)
def timesheet_stats(
    current_user: User = Depends(require_permission("timesheets.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    week_start = _week_start()

    my_q = db.query(TimesheetEntry).filter(
        TimesheetEntry.company_id == company.id,
        TimesheetEntry.employee_id == current_user.id,
    )
    my_pending = my_q.filter(TimesheetEntry.status == "submitted").count()
    my_week = my_q.filter(TimesheetEntry.work_date >= week_start, TimesheetEntry.status == "approved")
    my_hours = my_week.with_entities(func.coalesce(func.sum(TimesheetEntry.hours), 0)).scalar() or 0
    my_billable = (
        my_week.filter(TimesheetEntry.is_billable.is_(True))
        .with_entities(func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .scalar()
        or 0
    )

    pending_approval = 0
    team_hours = 0.0
    if role_has_permission(db, current_user.role, "timesheets.approve"):
        pending_approval = (
            db.query(TimesheetEntry)
            .filter(TimesheetEntry.company_id == company.id, TimesheetEntry.status == "submitted")
            .count()
        )
    if _user_has_view_all(current_user, db):
        team_hours = (
            db.query(func.coalesce(func.sum(TimesheetEntry.hours), 0))
            .filter(
                TimesheetEntry.company_id == company.id,
                TimesheetEntry.work_date >= week_start,
                TimesheetEntry.status == "approved",
            )
            .scalar()
            or 0
        )

    return TimesheetStatsResponse(
        my_pending_count=my_pending,
        my_hours_this_week=_float(my_hours),
        my_billable_hours_this_week=_float(my_billable),
        pending_approval_count=pending_approval,
        team_hours_this_week=_float(team_hours),
    )


@router.get("/approval-queue", response_model=TimesheetListResponse)
def approval_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_permission("timesheets.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    query = (
        db.query(TimesheetEntry)
        .options(
            joinedload(TimesheetEntry.employee),
            joinedload(TimesheetEntry.project),
            joinedload(TimesheetEntry.task),
            joinedload(TimesheetEntry.contact),
            joinedload(TimesheetEntry.reviewed_by),
        )
        .filter(TimesheetEntry.company_id == company.id, TimesheetEntry.status == "submitted")
        .order_by(TimesheetEntry.submitted_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return TimesheetListResponse(
        items=[_entry_resp(e) for e in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("", response_model=TimesheetListResponse)
def list_timesheets(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    mine: bool = Query(False),
    project_id: int | None = None,
    billable_only: bool = Query(False),
    search: str | None = None,
    current_user: User = Depends(require_permission("timesheets.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    query = (
        db.query(TimesheetEntry)
        .options(
            joinedload(TimesheetEntry.employee),
            joinedload(TimesheetEntry.project),
            joinedload(TimesheetEntry.task),
            joinedload(TimesheetEntry.contact),
            joinedload(TimesheetEntry.reviewed_by),
        )
        .filter(TimesheetEntry.company_id == company.id)
    )

    if mine or not _user_has_view_all(current_user, db):
        query = query.filter(TimesheetEntry.employee_id == current_user.id)
    if status:
        _validate_status(status)
        query = query.filter(TimesheetEntry.status == status)
    if project_id is not None:
        query = query.filter(TimesheetEntry.project_id == project_id)
    if billable_only:
        query = query.filter(TimesheetEntry.is_billable.is_(True))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                TimesheetEntry.description.ilike(term),
                TimesheetEntry.entry_number.ilike(term),
            )
        )

    query = query.order_by(TimesheetEntry.work_date.desc(), TimesheetEntry.id.desc())
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return TimesheetListResponse(items=[_entry_resp(e) for e in items], total=total, page=page, limit=limit)


@router.post("", response_model=TimesheetResponse)
def create_timesheet(
    payload: TimesheetCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("timesheets.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    _validate_hours(payload.hours)
    _validate_description(payload.description)

    project_id, task_id, contact_id = _validate_project_task(
        db, company.id, payload.project_id, payload.task_id
    )
    if payload.contact_id is not None:
        contact = db.query(Contact).filter(Contact.id == payload.contact_id, Contact.company_id == company.id).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Invalid contact")
        contact_id = contact.id

    entry = TimesheetEntry(
        company_id=company.id,
        employee_id=current_user.id,
        project_id=project_id,
        task_id=task_id,
        contact_id=contact_id,
        work_date=_date_only(payload.work_date),
        hours=payload.hours,
        is_billable=payload.is_billable,
        description=payload.description.strip(),
        status="draft",
    )
    db.add(entry)
    db.flush()

    if payload.submit:
        entry.entry_number = _generate_entry_number(db, company)
        entry.submitted_at = _utcnow()
        _transition(entry, "submitted")
        log_activity(
            db,
            action="timesheet_submitted",
            user_id=current_user.id,
            email=current_user.email,
            details=f"Submitted timesheet {entry.entry_number}",
            ip_address=get_client_ip(request),
        )
    else:
        log_activity(
            db,
            action="timesheet_created",
            user_id=current_user.id,
            email=current_user.email,
            details="Created timesheet draft",
            ip_address=get_client_ip(request),
        )

    db.commit()
    entry = _get_entry(db, entry.id, company.id)
    return _entry_resp(entry)


@router.get("/{entry_id}", response_model=TimesheetResponse)
def get_timesheet(
    entry_id: int,
    current_user: User = Depends(require_permission("timesheets.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    entry = _get_entry(db, entry_id, company.id)
    _ensure_access(db, current_user, entry)
    return _entry_resp(entry)


@router.put("/{entry_id}", response_model=TimesheetResponse)
def update_timesheet(
    entry_id: int,
    payload: TimesheetUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("timesheets.edit_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    entry = _get_entry(db, entry_id, company.id)
    if entry.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own timesheet entries")
    if entry.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Only draft or rejected entries can be edited")

    if payload.hours is not None:
        _validate_hours(payload.hours)
        entry.hours = payload.hours
    if payload.description is not None:
        _validate_description(payload.description)
        entry.description = payload.description.strip()
    if payload.work_date is not None:
        entry.work_date = _date_only(payload.work_date)
    if payload.is_billable is not None:
        entry.is_billable = payload.is_billable

    project_id = payload.project_id if payload.project_id is not None else entry.project_id
    task_id = payload.task_id if payload.task_id is not None else entry.task_id
    if payload.project_id is not None or payload.task_id is not None:
        project_id, task_id, auto_contact = _validate_project_task(db, company.id, project_id, task_id)
        entry.project_id = project_id
        entry.task_id = task_id
        if payload.contact_id is None and auto_contact:
            entry.contact_id = auto_contact
    if payload.contact_id is not None:
        contact = db.query(Contact).filter(Contact.id == payload.contact_id, Contact.company_id == company.id).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Invalid contact")
        entry.contact_id = contact.id

    if entry.status == "rejected":
        entry.reviewed_by_id = None
        entry.reviewed_at = None
        entry.reviewer_note = None

    db.commit()
    entry = _get_entry(db, entry.id, company.id)
    log_activity(
        db,
        action="timesheet_updated",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Updated timesheet {entry.entry_number or entry.id}",
        ip_address=get_client_ip(request),
    )
    return _entry_resp(entry)


@router.post("/{entry_id}/submit", response_model=TimesheetResponse)
def submit_timesheet(
    entry_id: int,
    request: Request,
    current_user: User = Depends(require_permission("timesheets.submit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    entry = _get_entry(db, entry_id, company.id)
    if entry.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the employee can submit this entry")
    if entry.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected entries can be submitted")

    _validate_description(entry.description)
    if not entry.entry_number:
        entry.entry_number = _generate_entry_number(db, company)
    entry.submitted_at = _utcnow()
    entry.reviewed_by_id = None
    entry.reviewed_at = None
    entry.reviewer_note = None
    _transition(entry, "submitted")

    db.commit()
    entry = _get_entry(db, entry.id, company.id)
    log_activity(
        db,
        action="timesheet_submitted",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Submitted timesheet {entry.entry_number}",
        ip_address=get_client_ip(request),
    )
    return _entry_resp(entry)


@router.post("/{entry_id}/approve", response_model=TimesheetResponse)
def approve_timesheet(
    entry_id: int,
    payload: TimesheetReviewRequest,
    request: Request,
    current_user: User = Depends(require_permission("timesheets.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    entry = _get_entry(db, entry_id, company.id)
    if entry.employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot approve your own timesheet entry")
    if entry.status != "submitted":
        raise HTTPException(status_code=400, detail="Only submitted entries can be approved")

    entry.reviewed_by_id = current_user.id
    entry.reviewed_at = _utcnow()
    entry.reviewer_note = payload.reviewer_note.strip() if payload.reviewer_note else None
    _transition(entry, "approved")

    db.commit()
    entry = _get_entry(db, entry.id, company.id)
    log_activity(
        db,
        action="timesheet_approved",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Approved timesheet {entry.entry_number}",
        ip_address=get_client_ip(request),
    )
    return _entry_resp(entry)


@router.post("/{entry_id}/reject", response_model=TimesheetResponse)
def reject_timesheet(
    entry_id: int,
    payload: TimesheetRejectRequest,
    request: Request,
    current_user: User = Depends(require_permission("timesheets.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    entry = _get_entry(db, entry_id, company.id)
    if entry.employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot reject your own timesheet entry")
    if entry.status != "submitted":
        raise HTTPException(status_code=400, detail="Only submitted entries can be rejected")

    note = (payload.reviewer_note or "").strip()
    if len(note) < 5:
        raise HTTPException(status_code=400, detail="Rejection note must be at least 5 characters")

    entry.reviewed_by_id = current_user.id
    entry.reviewed_at = _utcnow()
    entry.reviewer_note = note
    _transition(entry, "rejected")

    db.commit()
    entry = _get_entry(db, entry.id, company.id)
    log_activity(
        db,
        action="timesheet_rejected",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Rejected timesheet {entry.entry_number}",
        ip_address=get_client_ip(request),
    )
    return _entry_resp(entry)


@router.delete("/{entry_id}")
def delete_timesheet(
    entry_id: int,
    request: Request,
    current_user: User = Depends(require_permission("timesheets.delete_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    entry = _get_entry(db, entry_id, company.id)
    if entry.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own timesheet entries")
    if entry.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft entries can be deleted")

    db.delete(entry)
    db.commit()
    log_activity(
        db,
        action="timesheet_deleted",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Deleted timesheet draft {entry_id}",
        ip_address=get_client_ip(request),
    )
    return {"ok": True}


@router.post("/export-log")
def export_log(
    payload: TimesheetExportLogRequest,
    request: Request,
    current_user: User = Depends(require_permission("timesheets.export")),
    db: Session = Depends(get_db),
):
    log_activity(
        db,
        action="timesheet_export",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Exported timesheet data ({payload.row_count} rows)",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"ok": True}
