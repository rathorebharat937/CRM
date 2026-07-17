from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from leave_config import (
    ALLOWED_TRANSITIONS,
    EDITABLE_STATUSES,
    EMPLOYEE_CANCELLABLE_STATUSES,
    HALF_DAY_PERIOD_LABELS,
    HALF_DAY_PERIODS,
    LEAVE_STATUS_LABELS,
    LEAVE_STATUSES,
    LEAVE_TYPE_LABELS,
    LEAVE_TYPES,
    MIN_REASON_LENGTH,
    MIN_REJECTION_NOTE_LENGTH,
)
from models import Company, LeaveRequest, User
from services.workflow_events import emit_workflow_event
from permissions import role_has_permission
from config import STAFF_ROLES
from schemas import (
    LeaveCancelRequest,
    LeaveCreateRequest,
    LeaveExportLogRequest,
    LeaveListResponse,
    LeaveMetaResponse,
    LeaveOption,
    LeaveRejectRequest,
    LeaveResponse,
    LeaveReviewRequest,
    LeaveStatsResponse,
    LeaveUpdateRequest,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/leaves", tags=["leaves"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)




def _validate_leave_type(leave_type: str) -> None:
    if leave_type not in LEAVE_TYPES:
        raise HTTPException(status_code=400, detail=f"Leave type must be one of: {', '.join(LEAVE_TYPES)}")


def _validate_status(status: str) -> None:
    if status not in LEAVE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(LEAVE_STATUSES)}")


def _validate_half_day_period(period: str | None) -> None:
    if period is not None and period not in HALF_DAY_PERIODS:
        raise HTTPException(status_code=400, detail=f"Half-day period must be one of: {', '.join(HALF_DAY_PERIODS)}")


def _date_only(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.replace(hour=12, minute=0, second=0, microsecond=0)


def _compute_total_days(start_date: datetime, end_date: datetime, is_half_day: bool) -> float:
    if is_half_day:
        return 0.5
    start = _date_only(start_date).date()
    end = _date_only(end_date).date()
    return float((end - start).days + 1)


def _validate_dates(start_date: datetime, end_date: datetime, is_half_day: bool) -> None:
    start = _date_only(start_date)
    end = _date_only(end_date)
    if is_half_day and start.date() != end.date():
        raise HTTPException(status_code=400, detail="Half-day leave must use the same start and end date")
    if end < start:
        raise HTTPException(status_code=400, detail="End date must be on or after start date")


def _validate_reason(reason: str, *, required: bool = True) -> None:
    text = (reason or "").strip()
    if required and len(text) < MIN_REASON_LENGTH:
        raise HTTPException(status_code=400, detail=f"Reason must be at least {MIN_REASON_LENGTH} characters")


def _can_view_all(user: User, db: Session) -> bool:
    return role_has_permission(db, user.role, "leaves.view_all")


def _find_overlap(
    db: Session,
    company_id: int,
    employee_id: int,
    start_date: datetime,
    end_date: datetime,
    exclude_id: int | None = None,
) -> LeaveRequest | None:
    q = db.query(LeaveRequest).filter(
        LeaveRequest.company_id == company_id,
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.start_date <= _date_only(end_date),
        LeaveRequest.end_date >= _date_only(start_date),
    )
    if exclude_id:
        q = q.filter(LeaveRequest.id != exclude_id)
    return q.first()


def _overlap_warning(db: Session, leave: LeaveRequest) -> str | None:
    overlap = _find_overlap(
        db,
        leave.company_id,
        leave.employee_id,
        leave.start_date,
        leave.end_date,
        exclude_id=leave.id,
    )
    if not overlap:
        return None
    ref = overlap.leave_number or f"#{overlap.id}"
    return f"Overlaps with existing leave request {ref} ({overlap.status})"


def _generate_leave_number(db: Session, company: Company) -> str:
    year = _utcnow().year
    prefix = f"LV-{year}-"
    last = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.company_id == company.id, LeaveRequest.leave_number.like(f"{prefix}%"))
        .order_by(LeaveRequest.id.desc())
        .first()
    )
    seq = 1
    if last and last.leave_number:
        try:
            seq = int(last.leave_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _get_leave(db: Session, leave_id: int, company_id: int) -> LeaveRequest:
    leave = (
        db.query(LeaveRequest)
        .options(joinedload(LeaveRequest.employee), joinedload(LeaveRequest.reviewed_by))
        .filter(LeaveRequest.id == leave_id, LeaveRequest.company_id == company_id)
        .first()
    )
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return leave


def _ensure_access(db: Session, user: User, leave: LeaveRequest) -> None:
    if _can_view_all(user, db):
        return
    if leave.employee_id != user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this leave request")


def _leave_resp(db: Session, leave: LeaveRequest) -> LeaveResponse:
    return LeaveResponse(
        id=leave.id,
        leave_number=leave.leave_number,
        employee_id=leave.employee_id,
        employee_name=leave.employee.name if leave.employee else None,
        leave_type=leave.leave_type,
        leave_type_label=LEAVE_TYPE_LABELS.get(leave.leave_type, leave.leave_type),
        start_date=leave.start_date,
        end_date=leave.end_date,
        total_days=float(leave.total_days or 0),
        is_half_day=leave.is_half_day,
        half_day_period=leave.half_day_period,
        half_day_period_label=HALF_DAY_PERIOD_LABELS.get(leave.half_day_period) if leave.half_day_period else None,
        reason=leave.reason,
        status=leave.status,
        status_label=LEAVE_STATUS_LABELS.get(leave.status, leave.status),
        submitted_at=leave.submitted_at,
        reviewed_by_id=leave.reviewed_by_id,
        reviewed_by_name=leave.reviewed_by.name if leave.reviewed_by else None,
        reviewed_at=leave.reviewed_at,
        reviewer_note=leave.reviewer_note,
        overlap_warning=_overlap_warning(db, leave),
        created_at=leave.created_at,
        updated_at=leave.updated_at,
    )


def _transition(leave: LeaveRequest, new_status: str) -> None:
    _validate_status(new_status)
    allowed = ALLOWED_TRANSITIONS.get(leave.status, set())
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {leave.status} to {new_status}")
    leave.status = new_status


def _apply_payload(
    leave: LeaveRequest,
    *,
    leave_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    reason: str | None = None,
    is_half_day: bool | None = None,
    half_day_period: str | None = None,
) -> None:
    if leave_type is not None:
        _validate_leave_type(leave_type)
        leave.leave_type = leave_type
    if is_half_day is not None:
        leave.is_half_day = is_half_day
    if half_day_period is not None:
        _validate_half_day_period(half_day_period)
        leave.half_day_period = half_day_period if half_day_period else None
    if start_date is not None:
        leave.start_date = _date_only(start_date)
    if end_date is not None:
        leave.end_date = _date_only(end_date)
    if reason is not None:
        _validate_reason(reason)
        leave.reason = reason.strip()
    _validate_dates(leave.start_date, leave.end_date, leave.is_half_day)
    if leave.is_half_day and not leave.half_day_period:
        leave.half_day_period = "morning"
    leave.total_days = _compute_total_days(leave.start_date, leave.end_date, leave.is_half_day)


@router.get("/meta", response_model=LeaveMetaResponse)
def leave_meta(_: User = Depends(require_permission("leaves.view"))):
    return LeaveMetaResponse(
        leave_types=[LeaveOption(value=t, label=LEAVE_TYPE_LABELS[t]) for t in LEAVE_TYPES],
        statuses=[LeaveOption(value=s, label=LEAVE_STATUS_LABELS[s]) for s in LEAVE_STATUSES],
        half_day_periods=[LeaveOption(value=p, label=HALF_DAY_PERIOD_LABELS[p]) for p in HALF_DAY_PERIODS],
    )


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def leave_assignees(
    user: User = Depends(require_permission("leaves.view_all")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
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


@router.get("/stats/summary", response_model=LeaveStatsResponse)
def leave_stats(
    current_user: User = Depends(require_permission("leaves.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    base = db.query(LeaveRequest).filter(LeaveRequest.company_id == company.id)
    if not _can_view_all(current_user, db):
        base = base.filter(LeaveRequest.employee_id == current_user.id)

    now = _utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pending_q = db.query(LeaveRequest).filter(LeaveRequest.company_id == company.id, LeaveRequest.status == "pending")
    if not role_has_permission(db, current_user.role, "leaves.approve"):
        pending_q = pending_q.filter(LeaveRequest.employee_id == current_user.id)

    approved_month = base.filter(
        LeaveRequest.status == "approved",
        LeaveRequest.start_date >= month_start,
    ).all()

    team_end = now + timedelta(days=30)
    team_on_leave = (
        db.query(func.count(LeaveRequest.id))
        .filter(
            LeaveRequest.company_id == company.id,
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= team_end,
            LeaveRequest.end_date >= now,
        )
        .scalar()
        or 0
    )

    return LeaveStatsResponse(
        pending_count=pending_q.count(),
        approved_days_this_month=sum(float(l.total_days or 0) for l in approved_month),
        my_pending_count=base.filter(LeaveRequest.status == "pending").count(),
        team_on_leave_count=team_on_leave if _can_view_all(current_user, db) else 0,
    )


@router.get("/approval-queue", response_model=LeaveListResponse)
def approval_queue(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    leave_type: str | None = Query(None),
    search: str | None = Query(None),
    current_user: User = Depends(require_permission("leaves.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    q = (
        db.query(LeaveRequest)
        .options(joinedload(LeaveRequest.employee), joinedload(LeaveRequest.reviewed_by))
        .filter(LeaveRequest.company_id == company.id, LeaveRequest.status == "pending")
    )
    if leave_type:
        _validate_leave_type(leave_type)
        q = q.filter(LeaveRequest.leave_type == leave_type)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.join(LeaveRequest.employee).filter(
            or_(User.name.ilike(term), LeaveRequest.reason.ilike(term), LeaveRequest.leave_number.ilike(term))
        )
    total = q.count()
    items = q.order_by(LeaveRequest.submitted_at.asc().nullslast(), LeaveRequest.created_at.asc()).offset((page - 1) * limit).limit(limit).all()
    log_activity(
        db,
        action="leave_approval_queue_viewed",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Approval queue viewed ({total} pending)",
        ip_address=get_client_ip(request),
    )
    return LeaveListResponse(
        items=[_leave_resp(db, l) for l in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/team", response_model=LeaveListResponse)
def team_leave(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    employee_id: int | None = Query(None),
    leave_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_permission("leaves.view")),
    db: Session = Depends(get_db),
):
    if not _can_view_all(current_user, db):
        raise HTTPException(status_code=403, detail="Team leave view requires view_all permission")

    company = get_current_company(db, current_user)
    now = _utcnow()
    start = _date_only(date_from) if date_from else _date_only(now.replace(day=1))
    end = _date_only(date_to) if date_to else _date_only(now + timedelta(days=30))

    q = (
        db.query(LeaveRequest)
        .options(joinedload(LeaveRequest.employee), joinedload(LeaveRequest.reviewed_by))
        .filter(
            LeaveRequest.company_id == company.id,
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
    )
    if employee_id:
        q = q.filter(LeaveRequest.employee_id == employee_id)
    if leave_type:
        _validate_leave_type(leave_type)
        q = q.filter(LeaveRequest.leave_type == leave_type)

    total = q.count()
    items = q.order_by(LeaveRequest.start_date.asc()).offset((page - 1) * limit).limit(limit).all()
    return LeaveListResponse(items=[_leave_resp(db, l) for l in items], total=total, page=page, limit=limit)


@router.get("", response_model=LeaveListResponse)
def list_leaves(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    leave_type: str | None = Query(None),
    mine: bool = Query(False),
    search: str | None = Query(None),
    current_user: User = Depends(require_permission("leaves.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    q = (
        db.query(LeaveRequest)
        .options(joinedload(LeaveRequest.employee), joinedload(LeaveRequest.reviewed_by))
        .filter(LeaveRequest.company_id == company.id)
    )
    if mine or not _can_view_all(current_user, db):
        q = q.filter(LeaveRequest.employee_id == current_user.id)
    if status:
        _validate_status(status)
        q = q.filter(LeaveRequest.status == status)
    if leave_type:
        _validate_leave_type(leave_type)
        q = q.filter(LeaveRequest.leave_type == leave_type)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                LeaveRequest.reason.ilike(term),
                LeaveRequest.leave_number.ilike(term),
            )
        )

    total = q.count()
    items = q.order_by(LeaveRequest.start_date.desc()).offset((page - 1) * limit).limit(limit).all()

    log_activity(
        db,
        action="leave_list_viewed",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Leave list viewed ({total} records)",
        ip_address=get_client_ip(request),
    )

    return LeaveListResponse(
        items=[_leave_resp(db, l) for l in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=LeaveResponse)
def create_leave(
    payload: LeaveCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("leaves.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    _validate_leave_type(payload.leave_type)
    _validate_reason(payload.reason)
    _validate_half_day_period(payload.half_day_period)
    start = _date_only(payload.start_date)
    end = _date_only(payload.end_date)
    _validate_dates(start, end, payload.is_half_day)

    leave = LeaveRequest(
        company_id=company.id,
        employee_id=current_user.id,
        leave_type=payload.leave_type,
        start_date=start,
        end_date=end,
        total_days=_compute_total_days(start, end, payload.is_half_day),
        is_half_day=payload.is_half_day,
        half_day_period=payload.half_day_period or ("morning" if payload.is_half_day else None),
        reason=payload.reason.strip(),
        status="draft",
    )
    db.add(leave)
    db.flush()

    if payload.submit:
        _validate_reason(leave.reason)
        leave.leave_number = _generate_leave_number(db, company)
        leave.submitted_at = _utcnow()
        _transition(leave, "pending")
        log_activity(
            db,
            action="leave_submitted",
            user_id=current_user.id,
            email=current_user.email,
            details=f"Submitted leave {leave.leave_number}",
            ip_address=get_client_ip(request),
        )
    else:
        log_activity(
            db,
            action="leave_created",
            user_id=current_user.id,
            email=current_user.email,
            details="Created leave draft",
            ip_address=get_client_ip(request),
        )

    db.commit()
    leave = _get_leave(db, leave.id, company.id)
    return _leave_resp(db, leave)


@router.get("/{leave_id}", response_model=LeaveResponse)
def get_leave(
    leave_id: int,
    current_user: User = Depends(require_permission("leaves.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    leave = _get_leave(db, leave_id, company.id)
    _ensure_access(db, current_user, leave)
    return _leave_resp(db, leave)


@router.put("/{leave_id}", response_model=LeaveResponse)
def update_leave(
    leave_id: int,
    payload: LeaveUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("leaves.edit_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    leave = _get_leave(db, leave_id, company.id)
    _ensure_access(db, current_user, leave)

    if leave.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own leave requests")
    if leave.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Only draft or rejected leave requests can be edited")

    _apply_payload(
        leave,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        is_half_day=payload.is_half_day,
        half_day_period=payload.half_day_period,
    )

    if leave.status == "rejected":
        leave.reviewed_by_id = None
        leave.reviewed_at = None
        leave.reviewer_note = None

    db.commit()
    leave = _get_leave(db, leave.id, company.id)
    log_activity(
        db,
        action="leave_updated",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Updated leave {leave.leave_number or leave.id}",
        ip_address=get_client_ip(request),
    )
    return _leave_resp(db, leave)


@router.post("/{leave_id}/submit", response_model=LeaveResponse)
def submit_leave(
    leave_id: int,
    request: Request,
    current_user: User = Depends(require_permission("leaves.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    leave = _get_leave(db, leave_id, company.id)
    if leave.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the employee can submit this leave request")
    if leave.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected requests can be submitted")

    _validate_reason(leave.reason)
    if not leave.leave_number:
        leave.leave_number = _generate_leave_number(db, company)
    leave.submitted_at = _utcnow()
    leave.reviewed_by_id = None
    leave.reviewed_at = None
    leave.reviewer_note = None
    _transition(leave, "pending")

    db.commit()
    leave = _get_leave(db, leave.id, company.id)
    log_activity(
        db,
        action="leave_submitted",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Submitted leave {leave.leave_number}",
        ip_address=get_client_ip(request),
    )
    emit_workflow_event(
        db,
        company_id=company.id,
        trigger_type="leave.submitted",
        record_type="leave",
        record_id=leave.id,
        actor_id=current_user.id,
    )
    return _leave_resp(db, leave)


@router.post("/{leave_id}/approve", response_model=LeaveResponse)
def approve_leave(
    leave_id: int,
    payload: LeaveReviewRequest,
    request: Request,
    current_user: User = Depends(require_permission("leaves.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    leave = _get_leave(db, leave_id, company.id)
    if leave.employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot approve your own leave request")
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be approved")

    leave.reviewed_by_id = current_user.id
    leave.reviewed_at = _utcnow()
    leave.reviewer_note = payload.reviewer_note.strip() if payload.reviewer_note else None
    _transition(leave, "approved")

    db.commit()
    leave = _get_leave(db, leave.id, company.id)
    log_activity(
        db,
        action="leave_approved",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Approved leave {leave.leave_number}",
        ip_address=get_client_ip(request),
    )
    return _leave_resp(db, leave)


@router.post("/{leave_id}/reject", response_model=LeaveResponse)
def reject_leave(
    leave_id: int,
    payload: LeaveRejectRequest,
    request: Request,
    current_user: User = Depends(require_permission("leaves.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    leave = _get_leave(db, leave_id, company.id)
    if leave.employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot reject your own leave request")
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending leave requests can be rejected")

    note = payload.reviewer_note.strip()
    if len(note) < MIN_REJECTION_NOTE_LENGTH:
        raise HTTPException(status_code=400, detail=f"Rejection reason must be at least {MIN_REJECTION_NOTE_LENGTH} characters")

    leave.reviewed_by_id = current_user.id
    leave.reviewed_at = _utcnow()
    leave.reviewer_note = note
    _transition(leave, "rejected")

    db.commit()
    leave = _get_leave(db, leave.id, company.id)
    log_activity(
        db,
        action="leave_rejected",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Rejected leave {leave.leave_number}: {note}",
        ip_address=get_client_ip(request),
    )
    return _leave_resp(db, leave)


@router.post("/{leave_id}/cancel", response_model=LeaveResponse)
def cancel_leave(
    leave_id: int,
    payload: LeaveCancelRequest,
    request: Request,
    current_user: User = Depends(require_permission("leaves.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    leave = _get_leave(db, leave_id, company.id)
    _ensure_access(db, current_user, leave)

    is_owner = leave.employee_id == current_user.id
    can_cancel_all = role_has_permission(db, current_user.role, "leaves.cancel_all")
    can_cancel_own = role_has_permission(db, current_user.role, "leaves.cancel_own")

    if is_owner:
        if not can_cancel_own:
            raise HTTPException(status_code=403, detail="You do not have permission to cancel leave")
        if leave.status not in EMPLOYEE_CANCELLABLE_STATUSES:
            raise HTTPException(status_code=400, detail="You can only cancel draft or pending leave requests")
    elif can_cancel_all:
        if leave.status == "cancelled":
            raise HTTPException(status_code=400, detail="Leave request is already cancelled")
    else:
        raise HTTPException(status_code=403, detail="You do not have permission to cancel this leave request")

    _transition(leave, "cancelled")
    if payload.reason:
        leave.reviewer_note = payload.reason.strip()

    db.commit()
    leave = _get_leave(db, leave.id, company.id)
    log_activity(
        db,
        action="leave_cancelled",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Cancelled leave {leave.leave_number or leave.id}",
        ip_address=get_client_ip(request),
    )
    return _leave_resp(db, leave)


@router.post("/export-log")
def log_leave_export(
    payload: LeaveExportLogRequest,
    request: Request,
    current_user: User = Depends(require_permission("leaves.export")),
    db: Session = Depends(get_db),
):
    log_activity(
        db,
        action="leave_exported",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Exported leave data ({payload.row_count} rows)",
        ip_address=get_client_ip(request),
    )
    return {"ok": True}
