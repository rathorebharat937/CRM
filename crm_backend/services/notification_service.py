from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import Notification

VALID_TYPES = {"INFO", "SUCCESS", "WARNING", "ERROR"}


def create_notification(
    db: Session,
    title: str,
    message: str,
    notification_type: str = "INFO",
    user_id: int | None = None,
) -> Notification:
    """Create a notification. Pass user_id=None for global (visible to all)."""
    if notification_type not in VALID_TYPES:
        notification_type = "INFO"

    notification = Notification(
        title=title,
        message=message,
        type=notification_type,
        user_id=user_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_user_notifications(
    db: Session,
    user_id: int,
    page: int = 1,
    limit: int = 30,
) -> tuple[list[Notification], int]:
    """Return notifications visible to this user (own + global), newest first."""
    query = db.query(Notification).filter(
        or_(Notification.user_id == user_id, Notification.user_id.is_(None))
    )
    total = query.count()
    items = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def get_unread_count(db: Session, user_id: int) -> int:
    """Count unread notifications visible to this user."""
    return (
        db.query(Notification)
        .filter(
            or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
            Notification.is_read == False,  # noqa: E712
        )
        .count()
    )


def mark_as_read(db: Session, notification_id: int, user_id: int) -> Notification | None:
    """Mark a single notification as read if the user can see it."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
        )
        .first()
    )
    if notification:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_as_read(db: Session, user_id: int) -> int:
    """Mark all visible notifications as read. Returns count updated."""
    count = (
        db.query(Notification)
        .filter(
            or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
            Notification.is_read == False,  # noqa: E712
        )
        .update({Notification.is_read: True}, synchronize_session="fetch")
    )
    db.commit()
    return count
