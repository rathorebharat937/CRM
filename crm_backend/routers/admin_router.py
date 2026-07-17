from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from activity import log_activity
from auth_utils import (
    get_client_ip,
    get_db,
    hash_password,
    require_permission,
)
from permissions_data import ROLE_PERMISSIONS
from config import STAFF_ROLES
from models import ActivityLog, Permission, RolePermission, User
from tenant_utils import get_current_company, require_company_record
from schemas import (
    ActivityLogListResponse,
    ActivityLogResponse,
    AdminCreateUserRequest,
    AdminResetPasswordRequest,
    AdminUpdateUserRequest,
    RoleMatrixResponse,
    UserProfileResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/roles-matrix", response_model=RoleMatrixResponse)
def get_roles_matrix(
    _: User = Depends(require_permission("roles.view")),
    db: Session = Depends(get_db),
):
    permissions = db.query(Permission).order_by(Permission.module, Permission.code).all()
    matrix: dict[str, list[str]] = {}
    for role in ROLE_PERMISSIONS:
        rows = (
            db.query(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role == role)
            .order_by(Permission.code)
            .all()
        )
        matrix[role] = [row[0] for row in rows]

    return RoleMatrixResponse(
        roles=list(ROLE_PERMISSIONS.keys()),
        permissions=permissions,
        matrix=matrix,
    )


@router.get("/users", response_model=list[UserProfileResponse])
def list_users(
    role: str | None = Query(None),
    user: User = Depends(require_permission("users.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = db.query(User).filter(User.company_id == company.id).order_by(User.id)
    if role:
        query = query.filter(User.role == role)
    return query.all()


@router.post("/users", response_model=UserProfileResponse)
def create_staff_user(
    data: AdminCreateUserRequest,
    request: Request,
    admin: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db),
):
    if data.role not in STAFF_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Staff role must be Admin, Manager, Employee, Sales, or Accountant",
        )
    if data.status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="Status must be active or inactive")

    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if data.employee_id and db.query(User).filter(
        User.employee_id == data.employee_id
    ).first():
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    company = get_current_company(db, admin)

    user = User(
        company_id=company.id,
        employee_id=data.employee_id,
        name=data.name.strip(),
        email=email,
        phone=data.phone,
        password=hash_password(data.password),
        role=data.role,
        status=data.status,
        designation=data.designation,
        department=data.department,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_activity(
        db,
        "user_created",
        user_id=admin.id,
        email=admin.email,
        details=f"Created staff user {user.email} ({user.role})",
        ip_address=get_client_ip(request),
    )

    return user


@router.put("/users/{user_id}", response_model=UserProfileResponse)
def update_user(
    user_id: int,
    data: AdminUpdateUserRequest,
    request: Request,
    admin: User = Depends(require_permission("users.edit")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    require_company_record(user, get_current_company(db, admin).id, detail="User not found")

    if user.role == "User":
        raise HTTPException(
            status_code=400,
            detail="Public User accounts cannot be managed here",
        )

    old_status = user.status

    if data.name is not None:
        user.name = data.name.strip()
    if data.phone is not None:
        user.phone = data.phone
    if data.designation is not None:
        user.designation = data.designation
    if data.department is not None:
        user.department = data.department
    if data.employee_id is not None:
        existing = db.query(User).filter(
            User.employee_id == data.employee_id,
            User.id != user.id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Employee ID already exists")
        user.employee_id = data.employee_id
    if data.role is not None:
        if data.role not in STAFF_ROLES:
            raise HTTPException(
                status_code=400,
                detail="Staff role must be Admin, Manager, Employee, Sales, or Accountant",
            )
        user.role = data.role
    if data.status is not None:
        if data.status not in {"active", "inactive"}:
            raise HTTPException(status_code=400, detail="Status must be active or inactive")
        user.status = data.status

    db.commit()
    db.refresh(user)

    if data.status is not None and data.status != old_status:
        log_activity(
            db,
            "status_change",
            user_id=admin.id,
            email=admin.email,
            details=f"Changed {user.email} status from {old_status} to {user.status}",
            ip_address=get_client_ip(request),
        )
    else:
        log_activity(
            db,
            "user_updated",
            user_id=admin.id,
            email=admin.email,
            details=f"Updated staff user {user.email}",
            ip_address=get_client_ip(request),
        )

    return user


@router.put("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    data: AdminResetPasswordRequest,
    request: Request,
    admin: User = Depends(require_permission("users.reset_password")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    require_company_record(user, get_current_company(db, admin).id, detail="User not found")

    user.password = hash_password(data.new_password)
    db.commit()

    log_activity(
        db,
        "password_reset",
        user_id=admin.id,
        email=admin.email,
        details=f"Admin reset password for {user.email}",
        ip_address=get_client_ip(request),
    )

    return {"message": f"Password reset for {user.name}"}


@router.delete("/users/{user_id}", status_code=204)
def delete_staff_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require_permission("users.delete")),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    user = db.query(User).filter(User.id == user_id).first()
    require_company_record(user, get_current_company(db, admin).id, detail="User not found")
    if user.role == "User":
        raise HTTPException(status_code=400, detail="Use portal user management for public User accounts")
    email = user.email
    user.status = "inactive"
    db.commit()
    log_activity(
        db,
        "user_deleted",
        user_id=admin.id,
        email=admin.email,
        details=f"Deactivated staff user {email}",
        ip_address=get_client_ip(request),
    )


@router.get("/activity-logs/actions", response_model=list[str])
def list_activity_log_actions(
    _: User = Depends(require_permission("activity.view")),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ActivityLog.action)
        .distinct()
        .order_by(ActivityLog.action)
        .all()
    )
    return [row[0] for row in rows]


@router.get("/activity-logs", response_model=ActivityLogListResponse)
def list_activity_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = None,
    search: str | None = None,
    _: User = Depends(require_permission("activity.view")),
    db: Session = Depends(get_db),
):
    query = db.query(ActivityLog)

    if action:
        query = query.filter(ActivityLog.action == action.strip())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ActivityLog.email.ilike(term),
                ActivityLog.details.ilike(term),
                ActivityLog.action.ilike(term),
            )
        )

    total = query.count()
    items = (
        query.order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return ActivityLogListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )
