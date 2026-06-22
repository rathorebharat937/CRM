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
from services.notification_service import create_notification
from models import ActivityLog, Company, Permission, RolePermission, User
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
    _: User = Depends(require_permission("users.view")),
    db: Session = Depends(get_db),
):
    return db.query(User).order_by(User.id).all()


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
            detail="Staff role must be Admin, Manager, or Employee",
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

    company = db.query(Company).first()

    user = User(
        company_id=company.id if company else None,
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

    create_notification(db, "User Created", "A new employee account was created.", "SUCCESS")

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
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
                detail="Staff role must be Admin, Manager, or Employee",
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
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
