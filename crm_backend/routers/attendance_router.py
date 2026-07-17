from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from attendance_config import (
    ATTENDANCE_STATUS_LABELS,
    ATTENDANCE_STATUSES,
    STANDARD_CHECK_IN_HOUR,
    STANDARD_CHECK_IN_MINUTE,
)
from config import STAFF_ROLES
from models import AttendanceRecord, Company, User
from permissions import role_has_permission
from schemas import (
    AttendanceCheckInRequest,
    AttendanceListResponse,
    AttendanceMetaResponse,
    AttendanceRecordRequest,
    AttendanceResponse,
    AttendanceStatsResponse,
    AttendanceTeamTodayResponse,
    AttendanceTeamTodayRow,
    AttendanceTodayResponse,
    EmployeeOption,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])

DEMO_MARKER = "[demo-level4]"


def _is_demo_attendance(rec: AttendanceRecord | None) -> bool:
    return bool(rec and rec.notes and DEMO_MARKER in rec.notes)


def _is_self_checked_in(rec: AttendanceRecord | None) -> bool:
    return bool(rec and rec.check_in_at and not _is_demo_attendance(rec))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today_noon() -> datetime:
    now = _utcnow()
    return now.replace(hour=12, minute=0, second=0, microsecond=0)




def _float(v) -> float | None:
    return None if v is None else float(v)


def _attendance_resp(rec: AttendanceRecord) -> AttendanceResponse:
    return AttendanceResponse(
        id=rec.id,
        user_id=rec.user_id,
        user_name=rec.user.name if rec.user else None,
        attendance_date=rec.attendance_date,
        status=rec.status,
        status_label=ATTENDANCE_STATUS_LABELS.get(rec.status, rec.status),
        check_in_at=rec.check_in_at,
        check_out_at=rec.check_out_at,
        worked_hours=_float(rec.worked_hours),
        late_minutes=rec.late_minutes or 0,
        notes=rec.notes,
    )


@router.get("/meta", response_model=AttendanceMetaResponse)
def attendance_meta(_: User = Depends(require_permission("attendance.view"))):
    return AttendanceMetaResponse(
        statuses=[EmployeeOption(value=k, label=v) for k, v in ATTENDANCE_STATUS_LABELS.items()],
    )


@router.get("/stats/summary", response_model=AttendanceStatsResponse)
def attendance_stats(
    current_user: User = Depends(require_permission("attendance.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    today = _today_noon()
    base = db.query(AttendanceRecord).filter(
        AttendanceRecord.company_id == company.id,
        AttendanceRecord.attendance_date == today,
    )
    if not role_has_permission(db, current_user.role, "attendance.view_all"):
        mine = base.filter(AttendanceRecord.user_id == current_user.id).first()
        return AttendanceStatsResponse(my_status_today=mine.status if mine else None)

    return AttendanceStatsResponse(
        present_today=base.filter(AttendanceRecord.status == "present").count(),
        absent_today=base.filter(AttendanceRecord.status == "absent").count(),
        late_today=base.filter(AttendanceRecord.status == "late").count(),
        on_leave_today=base.filter(AttendanceRecord.status == "on_leave").count(),
    )


@router.get("/today", response_model=AttendanceTodayResponse)
def my_attendance_today(
    current_user: User = Depends(require_permission("attendance.view")),
    db: Session = Depends(get_db),
):
    """Today's attendance for the logged-in employee with check-in/out actions."""
    company = get_current_company(db, current_user)
    today = _today_noon()
    rec = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.company_id == company.id,
            AttendanceRecord.user_id == current_user.id,
            AttendanceRecord.attendance_date == today,
        )
        .first()
    )
    if _is_demo_attendance(rec):
        rec = None

    can_check_in = role_has_permission(db, current_user.role, "attendance.check_in") and (
        rec is None or rec.check_in_at is None
    )
    can_check_out = role_has_permission(db, current_user.role, "attendance.check_in") and (
        rec is not None and rec.check_in_at is not None and rec.check_out_at is None
    )
    if not rec:
        return AttendanceTodayResponse(
            attendance_date=today,
            has_record=False,
            status_label="Not checked in",
            can_check_in=can_check_in,
            can_check_out=False,
        )
    return AttendanceTodayResponse(
        attendance_date=today,
        has_record=True,
        status=rec.status,
        status_label=ATTENDANCE_STATUS_LABELS.get(rec.status, rec.status),
        check_in_at=rec.check_in_at,
        check_out_at=rec.check_out_at,
        worked_hours=_float(rec.worked_hours),
        late_minutes=rec.late_minutes or 0,
        can_check_in=can_check_in,
        can_check_out=can_check_out,
    )


@router.get("/team/today", response_model=AttendanceTeamTodayResponse)
def team_attendance_today(
    current_user: User = Depends(require_permission("attendance.view_all")),
    db: Session = Depends(get_db),
):
    """All staff attendance for today — visible to Admin and Manager."""
    company = get_current_company(db, current_user)
    today = _today_noon()
    staff = (
        db.query(User)
        .filter(User.company_id == company.id, User.role.in_(list(STAFF_ROLES)), User.status == "active")
        .order_by(User.name)
        .all()
    )
    records = {
        r.user_id: r
        for r in db.query(AttendanceRecord)
        .filter(AttendanceRecord.company_id == company.id, AttendanceRecord.attendance_date == today)
        .all()
    }
    rows: list[AttendanceTeamTodayRow] = []
    checked_in = 0
    checked_out = 0
    for user in staff:
        rec = records.get(user.id)
        if _is_demo_attendance(rec):
            rec = None
        if rec and rec.check_in_at:
            checked_in += 1
        if rec and rec.check_out_at:
            checked_out += 1
        if rec:
            status_label = ATTENDANCE_STATUS_LABELS.get(rec.status, rec.status)
            if rec.check_out_at:
                status_label = f"{status_label} · Day complete"
            elif rec.check_in_at:
                status_label = f"{status_label} · Working"
        else:
            status_label = "Not checked in"
        rows.append(
            AttendanceTeamTodayRow(
                user_id=user.id,
                user_name=user.name,
                department=user.department,
                role=user.role,
                status=rec.status if rec else None,
                status_label=status_label,
                check_in_at=rec.check_in_at if rec else None,
                check_out_at=rec.check_out_at if rec else None,
                worked_hours=_float(rec.worked_hours) if rec else None,
                late_minutes=rec.late_minutes if rec else 0,
            )
        )
    return AttendanceTeamTodayResponse(
        attendance_date=today,
        items=rows,
        total_staff=len(staff),
        checked_in_count=checked_in,
        checked_out_count=checked_out,
    )


@router.get("", response_model=AttendanceListResponse)
def list_attendance(
    page: int = Query(1, ge=1),
    limit: int = Query(31, ge=1, le=100),
    user_id: int | None = None,
    days: int = Query(14, ge=1, le=90),
    current_user: User = Depends(require_permission("attendance.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    since = _today_noon() - timedelta(days=days)
    query = (
        db.query(AttendanceRecord)
        .options(joinedload(AttendanceRecord.user))
        .filter(AttendanceRecord.company_id == company.id, AttendanceRecord.attendance_date >= since)
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.id.desc())
    )
    if user_id is not None:
        if user_id != current_user.id and not role_has_permission(db, current_user.role, "attendance.view_all"):
            raise HTTPException(status_code=403, detail="Permission denied")
        query = query.filter(AttendanceRecord.user_id == user_id)
    elif not role_has_permission(db, current_user.role, "attendance.view_all"):
        query = query.filter(AttendanceRecord.user_id == current_user.id)

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return AttendanceListResponse(
        items=[_attendance_resp(r) for r in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=AttendanceResponse)
def record_attendance(
    payload: AttendanceRecordRequest,
    request: Request,
    current_user: User = Depends(require_permission("attendance.record")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    if payload.status not in ATTENDANCE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    att_date = payload.attendance_date.replace(hour=12, minute=0, second=0, microsecond=0)
    existing = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.company_id == company.id,
            AttendanceRecord.user_id == payload.user_id,
            AttendanceRecord.attendance_date == att_date,
        )
        .first()
    )
    worked = None
    if payload.check_in_at and payload.check_out_at:
        worked = round((payload.check_out_at - payload.check_in_at).total_seconds() / 3600, 2)

    if existing:
        existing.status = payload.status
        existing.check_in_at = payload.check_in_at
        existing.check_out_at = payload.check_out_at
        existing.worked_hours = worked
        existing.notes = payload.notes
        existing.recorded_by_id = current_user.id
        rec = existing
    else:
        rec = AttendanceRecord(
            company_id=company.id,
            user_id=payload.user_id,
            attendance_date=att_date,
            status=payload.status,
            check_in_at=payload.check_in_at,
            check_out_at=payload.check_out_at,
            worked_hours=worked,
            notes=payload.notes,
            recorded_by_id=current_user.id,
        )
        db.add(rec)

    db.commit()
    rec = db.query(AttendanceRecord).options(joinedload(AttendanceRecord.user)).filter(AttendanceRecord.id == rec.id).first()
    log_activity(db, action="attendance_recorded", user_id=current_user.id, email=current_user.email,
                 details=f"Recorded attendance for user {payload.user_id}", ip_address=get_client_ip(request))
    return _attendance_resp(rec)


@router.post("/check-in", response_model=AttendanceResponse)
def check_in(
    payload: AttendanceCheckInRequest,
    request: Request,
    current_user: User = Depends(require_permission("attendance.check_in")),
    db: Session = Depends(get_db),
):
    if role_has_permission(db, current_user.role, "attendance.view_all"):
        raise HTTPException(
            status_code=403,
            detail="Use your employee login to check in. This account is for viewing team attendance only.",
        )
    company = get_current_company(db, current_user)
    today = _today_noon()
    now = _utcnow()
    rec = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.company_id == company.id,
            AttendanceRecord.user_id == current_user.id,
            AttendanceRecord.attendance_date == today,
        )
        .first()
    )
    if _is_demo_attendance(rec):
        db.delete(rec)
        db.flush()
        rec = None
    elif rec and rec.check_in_at:
        raise HTTPException(status_code=400, detail="Already checked in today")

    standard = now.replace(hour=STANDARD_CHECK_IN_HOUR, minute=STANDARD_CHECK_IN_MINUTE, second=0, microsecond=0)
    late_mins = max(0, int((now - standard).total_seconds() // 60)) if now > standard else 0
    status = "late" if late_mins > 0 else "present"

    if not rec:
        rec = AttendanceRecord(
            company_id=company.id,
            user_id=current_user.id,
            attendance_date=today,
            status=status,
            check_in_at=now,
            late_minutes=late_mins,
            notes=payload.notes.strip() if payload.notes else "Self check-in",
        )
        db.add(rec)
    else:
        rec.check_in_at = now
        rec.check_out_at = None
        rec.worked_hours = None
        rec.status = status
        rec.late_minutes = late_mins
        rec.notes = payload.notes.strip() if payload.notes else "Self check-in"
        rec.recorded_by_id = None

    db.commit()
    rec = db.query(AttendanceRecord).options(joinedload(AttendanceRecord.user)).filter(AttendanceRecord.id == rec.id).first()
    log_activity(db, action="attendance_check_in", user_id=current_user.id, email=current_user.email,
                 details="Checked in", ip_address=get_client_ip(request))
    return _attendance_resp(rec)


@router.post("/check-out", response_model=AttendanceResponse)
def check_out(
    request: Request,
    current_user: User = Depends(require_permission("attendance.check_in")),
    db: Session = Depends(get_db),
):
    if role_has_permission(db, current_user.role, "attendance.view_all"):
        raise HTTPException(
            status_code=403,
            detail="Use your employee login to check out. This account is for viewing team attendance only.",
        )
    company = get_current_company(db, current_user)
    today = _today_noon()
    now = _utcnow()
    rec = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.company_id == company.id,
            AttendanceRecord.user_id == current_user.id,
            AttendanceRecord.attendance_date == today,
        )
        .first()
    )
    if _is_demo_attendance(rec):
        raise HTTPException(status_code=400, detail="Check in first")
    if not rec or not rec.check_in_at:
        raise HTTPException(status_code=400, detail="Check in first")
    if rec.check_out_at:
        raise HTTPException(status_code=400, detail="Already checked out")

    rec.check_out_at = now
    rec.worked_hours = round((now - rec.check_in_at).total_seconds() / 3600, 2)
    db.commit()
    rec = db.query(AttendanceRecord).options(joinedload(AttendanceRecord.user)).filter(AttendanceRecord.id == rec.id).first()
    log_activity(db, action="attendance_check_out", user_id=current_user.id, email=current_user.email,
                 details="Checked out", ip_address=get_client_ip(request))
    return _attendance_resp(rec)
