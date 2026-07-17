from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import STAFF_ROLES
from employee_config import EMPLOYMENT_TYPE_LABELS, EMPLOYMENT_TYPES, GENDER_LABELS, GENDERS
from models import Company, EmployeeProfile, User
from permissions import role_has_permission
from schemas import (
    EmployeeListResponse,
    EmployeeMetaResponse,
    EmployeeOption,
    EmployeeProfileResponse,
    EmployeeProfileUpdateRequest,
)

router = APIRouter(prefix="/employees", tags=["employees"])




def _float(v) -> float | None:
    return None if v is None else float(v)


def _employee_resp(user: User, profile: EmployeeProfile | None) -> EmployeeProfileResponse:
    return EmployeeProfileResponse(
        id=profile.id if profile else None,
        user_id=user.id,
        employee_id=user.employee_id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        designation=user.designation,
        department=user.department,
        joining_date=profile.joining_date if profile else None,
        date_of_birth=profile.date_of_birth if profile else None,
        gender=profile.gender if profile else None,
        gender_label=GENDER_LABELS.get(profile.gender) if profile and profile.gender else None,
        employment_type=profile.employment_type if profile else None,
        employment_type_label=EMPLOYMENT_TYPE_LABELS.get(profile.employment_type) if profile else None,
        manager_id=profile.manager_id if profile else None,
        manager_name=profile.manager.name if profile and profile.manager else None,
        salary_monthly=_float(profile.salary_monthly) if profile else None,
        emergency_contact_name=profile.emergency_contact_name if profile else None,
        emergency_contact_phone=profile.emergency_contact_phone if profile else None,
        address_line1=profile.address_line1 if profile else None,
        city=profile.city if profile else None,
        state=profile.state if profile else None,
        pincode=profile.pincode if profile else None,
        pan=profile.pan if profile else None,
        bank_name=profile.bank_name if profile else None,
        bank_account_last4=profile.bank_account_last4 if profile else None,
        notes=profile.notes if profile else None,
        last_login_at=user.last_login_at,
    )


@router.get("/meta", response_model=EmployeeMetaResponse)
def employee_meta(_: User = Depends(require_permission("employees.view"))):
    return EmployeeMetaResponse(
        employment_types=[EmployeeOption(value=k, label=v) for k, v in EMPLOYMENT_TYPE_LABELS.items()],
        genders=[EmployeeOption(value=k, label=v) for k, v in GENDER_LABELS.items()],
    )


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    department: str | None = None,
    current_user: User = Depends(require_permission("employees.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    if not role_has_permission(db, current_user.role, "employees.view_all"):
        user = db.query(User).filter(User.id == current_user.id).first()
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()
        return EmployeeListResponse(
            items=[_employee_resp(user, profile)],
            total=1,
            page=1,
            limit=1,
        )

    query = (
        db.query(User)
        .filter(User.company_id == company.id, User.role.in_(list(STAFF_ROLES)))
        .order_by(User.name)
    )
    if department:
        query = query.filter(User.department == department)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(User.name.ilike(term), User.email.ilike(term), User.employee_id.ilike(term)))

    total = query.count()
    users = query.offset((page - 1) * limit).limit(limit).all()
    user_ids = [u.id for u in users]
    profiles = {
        p.user_id: p
        for p in db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.manager))
        .filter(EmployeeProfile.user_id.in_(user_ids))
        .all()
    }
    return EmployeeListResponse(
        items=[_employee_resp(u, profiles.get(u.id)) for u in users],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{user_id}", response_model=EmployeeProfileResponse)
def get_employee(
    user_id: int,
    current_user: User = Depends(require_permission("employees.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    if user_id != current_user.id and not role_has_permission(db, current_user.role, "employees.view_all"):
        raise HTTPException(status_code=403, detail="Permission denied")

    user = db.query(User).filter(User.id == user_id, User.company_id == company.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    profile = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.manager))
        .filter(EmployeeProfile.user_id == user_id, EmployeeProfile.company_id == company.id)
        .first()
    )
    return _employee_resp(user, profile)


@router.put("/{user_id}/profile", response_model=EmployeeProfileResponse)
def upsert_employee_profile(
    user_id: int,
    payload: EmployeeProfileUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("employees.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    user = db.query(User).filter(User.id == user_id, User.company_id == company.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    if payload.designation is not None:
        user.designation = payload.designation.strip() or None
    if payload.department is not None:
        user.department = payload.department.strip() or None

    profile = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.user_id == user_id, EmployeeProfile.company_id == company.id)
        .first()
    )
    if not profile:
        profile = EmployeeProfile(company_id=company.id, user_id=user_id)
        db.add(profile)

    if payload.employment_type and payload.employment_type not in EMPLOYMENT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid employment type")
    if payload.gender and payload.gender not in GENDERS:
        raise HTTPException(status_code=400, detail="Invalid gender")

    for field in (
        "joining_date", "date_of_birth", "gender", "employment_type", "manager_id",
        "emergency_contact_name", "emergency_contact_phone", "address_line1", "city",
        "state", "pincode", "pan", "bank_name", "bank_account_last4", "notes",
    ):
        val = getattr(payload, field)
        if val is not None:
            setattr(profile, field, val.strip() if isinstance(val, str) else val)
    if payload.salary_monthly is not None:
        profile.salary_monthly = payload.salary_monthly

    db.commit()
    profile = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.manager))
        .filter(EmployeeProfile.id == profile.id)
        .first()
    )
    user = db.query(User).filter(User.id == user_id).first()
    log_activity(
        db,
        action="employee_profile_updated",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Updated HR profile for {user.email}",
        ip_address=get_client_ip(request),
    )
    return _employee_resp(user, profile)
