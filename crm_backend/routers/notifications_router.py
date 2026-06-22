from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth_utils import get_current_user, get_db, require_admin
from models import User
from notification_schemas import (
    NotificationCreateRequest,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from services.notification_service import (
    create_notification,
    get_unread_count,
    get_user_notifications,
    mark_all_as_read,
    mark_as_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's notifications (own + global)."""
    items, total = get_user_notifications(db, user.id, page, limit)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the count of unread notifications for the current user."""
    return UnreadCountResponse(count=get_unread_count(db, user.id))


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    notification = mark_as_read(db, notification_id, user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationResponse.model_validate(notification)


@router.patch("/read-all")
def read_all_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all visible notifications as read."""
    count = mark_all_as_read(db, user.id)
    return {"message": f"Marked {count} notifications as read"}


@router.post("", response_model=NotificationResponse, status_code=201)
def create_new_notification(
    data: NotificationCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: create a notification."""
    valid_types = {"INFO", "SUCCESS", "WARNING", "ERROR"}
    notification_type = data.type.upper()
    if notification_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Type must be one of: {', '.join(sorted(valid_types))}",
        )

    notification = create_notification(
        db,
        title=data.title,
        message=data.message,
        notification_type=notification_type,
        user_id=data.user_id,
    )
    return NotificationResponse.model_validate(notification)
