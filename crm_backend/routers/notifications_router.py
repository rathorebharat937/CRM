from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import STAFF_ROLES
from models import Company, Notification, User
from schemas import (
    NotificationListResponse,
    NotificationResponse,
    NotificationRolesResponse,
    NotificationSendRequest,
    NotificationSendResponse,
    NotificationUnreadCountResponse,
)
from services.notification_service import notify_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

NOTIFICATION_CATEGORIES = {"announcement", "follow_up", "approval", "payment", "task", "system"}




def _serialize(note: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=note.id,
        category=note.category,
        title=note.title,
        message=note.message,
        link_path=note.link_path,
        is_read=note.is_read,
        created_at=note.created_at,
    )


def _recipient_role_options(current_user: User) -> list[str]:
    """Roles a sender may target — never their own role (no self-group broadcasts)."""
    options = sorted(STAFF_ROLES) + ["User"]
    return [r for r in options if r != current_user.role]


@router.get("/roles", response_model=NotificationRolesResponse)
def list_notification_roles(
    current_user: User = Depends(require_permission("notifications.send")),
):
    return NotificationRolesResponse(roles=_recipient_role_options(current_user))


@router.post("/send", response_model=NotificationSendResponse)
def send_notifications(
    payload: NotificationSendRequest,
    request: Request,
    current_user: User = Depends(require_permission("notifications.send")),
    db: Session = Depends(get_db),
):
    """Send an in-app alert to all active users in one role. Staff may target portal User accounts; User role cannot send."""
    company = get_current_company(db, current_user)
    target = payload.target_role.strip()

    if payload.category not in NOTIFICATION_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid notification category")

    if target == current_user.role:
        raise HTTPException(
            status_code=400,
            detail="You cannot send an alert to your own role — choose another group",
        )

    if target == "all_staff":
        users = (
            db.query(User)
            .filter(
                User.company_id == company.id,
                User.status == "active",
                User.role.in_(list(STAFF_ROLES)),
            )
            .all()
        )
        target_label = "all_staff"
    elif target == "User":
        users = (
            db.query(User)
            .filter(
                User.company_id == company.id,
                User.status == "active",
                User.role == "User",
            )
            .all()
        )
        target_label = "User"
    else:
        if target not in STAFF_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"target_role must be one of: all_staff, User, {', '.join(sorted(STAFF_ROLES))}",
            )
        users = (
            db.query(User)
            .filter(
                User.company_id == company.id,
                User.status == "active",
                User.role == target,
            )
            .all()
        )
        target_label = target

    if not users:
        raise HTTPException(status_code=400, detail="No active users found for that role")

    link = payload.link_path.strip() if payload.link_path else None
    for user in users:
        notify_user(
            db,
            company_id=company.id,
            user_id=user.id,
            category=payload.category,
            title=payload.title.strip(),
            message=payload.message.strip(),
            link_path=link,
        )
    db.commit()

    log_activity(
        db,
        "notifications_sent",
        user_id=current_user.id,
        email=current_user.email,
        details=f"Sent '{payload.title.strip()}' to {target_label} ({len(users)} recipients)",
        ip_address=get_client_ip(request),
    )

    return NotificationSendResponse(
        recipient_count=len(users),
        target_role=target_label,
        message=f"Notification sent to {len(users)} user(s).",
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = Query(True),
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(require_permission("notifications.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    query = (
        db.query(Notification)
        .filter(Notification.company_id == company.id, Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    items = query.limit(limit).all()
    unread = (
        db.query(Notification)
        .filter(
            Notification.company_id == company.id,
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .count()
    )
    return NotificationListResponse(items=[_serialize(n) for n in items], unread_count=unread)


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def unread_count(
    current_user: User = Depends(require_permission("notifications.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    count = (
        db.query(Notification)
        .filter(
            Notification.company_id == company.id,
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .count()
    )
    return NotificationUnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def dismiss_notification(
    notification_id: int,
    current_user: User = Depends(require_permission("notifications.view")),
    db: Session = Depends(get_db),
):
    """Remove an alert from the user's inbox after it has been read or opened."""
    company = get_current_company(db, current_user)
    note = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.company_id == company.id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Notification not found")
    data = _serialize(note)
    db.delete(note)
    db.commit()
    return data


@router.post("/read-all")
def dismiss_all_notifications(
    current_user: User = Depends(require_permission("notifications.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    db.query(Notification).filter(
        Notification.company_id == company.id,
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
    ).delete(synchronize_session=False)
    db.commit()
    return {"success": True}
