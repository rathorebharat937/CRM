from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import Company, Notification, User


def _utc_today_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _already_notified_today(
    db: Session,
    *,
    company_id: int,
    user_id: int,
    category: str,
    title: str,
) -> bool:
    """Skip duplicate alerts for the same user/category/title within the UTC day."""
    return (
        db.query(Notification.id)
        .filter(
            Notification.company_id == company_id,
            Notification.user_id == user_id,
            Notification.category == category,
            Notification.title == title,
            Notification.created_at >= _utc_today_start(),
        )
        .first()
        is not None
    )


def notify_user(
    db: Session,
    *,
    company_id: int,
    user_id: int,
    category: str,
    title: str,
    message: str,
    link_path: str | None = None,
    dedupe_per_day: bool = False,
) -> Notification | None:
    if dedupe_per_day and _already_notified_today(
        db,
        company_id=company_id,
        user_id=user_id,
        category=category,
        title=title,
    ):
        return None
    note = Notification(
        company_id=company_id,
        user_id=user_id,
        category=category,
        title=title,
        message=message,
        link_path=link_path,
        is_read=False,
    )
    db.add(note)
    db.flush()
    return note


def notify_role(
    db: Session,
    *,
    company_id: int,
    role: str,
    category: str,
    title: str,
    message: str,
    link_path: str | None = None,
    dedupe_per_day: bool = False,
) -> list[Notification]:
    users = (
        db.query(User)
        .filter(User.company_id == company_id, User.role == role, User.status == "active")
        .all()
    )
    created: list[Notification] = []
    for user in users:
        note = notify_user(
            db,
            company_id=company_id,
            user_id=user.id,
            category=category,
            title=title,
            message=message,
            link_path=link_path,
            dedupe_per_day=dedupe_per_day,
        )
        if note:
            created.append(note)
    return created


def get_company_id(db: Session) -> int | None:
    company = db.query(Company).first()
    return company.id if company else None
