from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from activity import log_activity
from auth_utils import (
    create_access_token,
    get_client_ip,
    get_current_user,
    get_db,
    hash_password,
    require_permission,
    verify_password,
)
from models import ActivityLog, Company, User
from permissions import get_permissions_for_role
from schemas import (
    ActivityLogListResponse,
    ActivityLogResponse,
    ChangePasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterCompanyRequest,
    RegisterCompanyResponse,
    SignupRequest,
    TokenResponse,
    UserProfileResponse,
)
from services.tenant_bootstrap_service import create_company_with_admin

router = APIRouter(tags=["auth"])
from config import FRONTEND_URL
from services.email_service import send_email, render_template

# Duplicate verify endpoint removed – definition moved later in file

def _token_response(user: User, message: str, db: Session) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user),
        message=message,
        role=user.role,
        name=user.name,
        email=user.email,
        company_id=user.company_id,
        permissions=get_permissions_for_role(db, user.role),
    )


@router.post("/register-company", response_model=RegisterCompanyResponse)
def register_company(data: RegisterCompanyRequest, request: Request, db: Session = Depends(get_db)):
    email = data.owner_email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    display_name = (data.company_display_name or data.company_legal_name).strip()
    try:
        company, admin = create_company_with_admin(
            db,
            legal_name=data.company_legal_name.strip(),
            display_name=display_name,
            owner_name=data.owner_name,
            owner_email=email,
            password_hash=hash_password(data.password),
            phone=data.phone,
        )
        db.commit()
        db.refresh(company)
        db.refresh(admin)
    except Exception:
        db.rollback()
        raise

    log_activity(
        db,
        "company_registered",
        user_id=admin.id,
        email=admin.email,
        details=f"Registered company {company.display_name}",
        ip_address=get_client_ip(request),
    )

    return RegisterCompanyResponse(
        access_token=create_access_token(admin),
        message="Company registered successfully",
        role=admin.role,
        name=admin.name,
        email=admin.email,
        company_id=company.id,
        company_name=company.display_name,
        permissions=get_permissions_for_role(db, admin.role),
    )


@router.post("/signup", response_model=TokenResponse)
def signup(data: SignupRequest, request: Request, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=403,
        detail="Public portal signup is disabled. Register your business or ask your admin for an invite.",
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    user = db.query(User).filter(User.email == email).first()
    ip = get_client_ip(request)

    if not user:
        log_activity(
            db,
            "login_failed",
            email=email,
            details="Invalid email",
            ip_address=ip,
        )
        raise HTTPException(status_code=401, detail="Invalid Email")

    if user.status != "active":
        log_activity(
            db,
            "login_failed",
            user_id=user.id,
            email=email,
            details="Inactive account",
            ip_address=ip,
        )
        raise HTTPException(status_code=403, detail="Account is inactive")

    if not verify_password(data.password, user.password):
        log_activity(
            db,
            "login_failed",
            user_id=user.id,
            email=email,
            details="Invalid password",
            ip_address=ip,
        )
        raise HTTPException(status_code=401, detail="Invalid Password")

    if user.role != "User" and user.company_id is None:
        raise HTTPException(
            status_code=403,
            detail="No company workspace assigned. Register your business or contact support.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    log_activity(
        db,
        "login_success",
        user_id=user.id,
        email=user.email,
        ip_address=ip,
    )

    return _token_response(user, "Login Success", db)


@router.post("/logout")
def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log_activity(
        db,
        "logout",
        user_id=user.id,
        email=user.email,
        ip_address=get_client_ip(request),
    )
    return {"message": "Logged out"}


@router.get("/users/me/permissions")
def get_my_permissions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"permissions": get_permissions_for_role(db, user.role)}


@router.get("/users/me", response_model=UserProfileResponse)
def get_profile(user: User = Depends(require_permission("profile.view"))):
    return user


@router.get("/users/me/activity", response_model=ActivityLogListResponse)
def my_activity(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ActivityLog).filter(ActivityLog.user_id == user.id)
    total = query.count()
    items = (
        query.order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ActivityLogListResponse(items=items, total=total, page=page, limit=limit)


@router.put("/users/me", response_model=UserProfileResponse)
def update_profile(
    data: ProfileUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("profile.edit")),
    db: Session = Depends(get_db),
):
    user.name = data.name.strip()
    user.phone = data.phone
    db.commit()
    db.refresh(user)

    log_activity(
        db,
        "profile_update",
        user_id=user.id,
        email=user.email,
        ip_address=get_client_ip(request),
    )

    return user


@router.put("/users/me/password")
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    user: User = Depends(require_permission("profile.change_password")),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password = hash_password(data.new_password)
    db.commit()

    log_activity(
        db,
        "password_change",
        user_id=user.id,
        email=user.email,
        ip_address=get_client_ip(request),
    )

    return {"message": "Password updated successfully"}

# --------------------------------------------------
# Password Reset Endpoints
# --------------------------------------------------

# Import additional utilities for password reset

from schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    VerifyResetTokenResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
import secrets

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate a reset token and email it to the user (if exists)."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    # Always respond with success to avoid email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
        user.reset_token = token
        user.reset_token_expiry = expiry
        db.commit()
        # Build reset URL for frontend
        reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
        html_body = render_template(
            "reset_password.html",
            crm_name="BlackPapers CRM",
            user_name=user.name,
            reset_url=reset_link,
            year=datetime.now().year,
        )
        send_email(
            to=user.email,
            subject="Password Reset – BlackPapers CRM",
            html_body=html_body,
        )
        log_activity(
            db,
            "forgot_password",
            user_id=user.id,
            email=user.email,
            ip_address=get_client_ip(request),
        )
    return ForgotPasswordResponse()

@router.get("/verify-reset-token/{token}", response_model=VerifyResetTokenResponse)
def verify_reset_token(token: str, db: Session = Depends(get_db)):
    """Check if a reset token is still valid (exists and not expired)."""
    user = (
        db.query(User)
        .filter(User.reset_token == token, User.reset_token_expiry > datetime.now(timezone.utc))
        .first()
    )
    return VerifyResetTokenResponse(valid=bool(user))

@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate token, update password, and clear token fields."""
    user = (
        db.query(User)
        .filter(User.reset_token == payload.token, User.reset_token_expiry > datetime.now(timezone.utc))
        .first()
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    user.password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()
    log_activity(
        db,
        "password_reset",
        user_id=user.id,
        email=user.email,
        ip_address=get_client_ip(request),
    )
    # Return updated user profile info
    return ResetPasswordResponse(
        id=user.id,
        company_id=user.company_id,
        employee_id=user.employee_id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        designation=user.designation,
        department=user.department,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )

