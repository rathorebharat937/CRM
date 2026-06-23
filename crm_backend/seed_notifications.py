"""Seed sample notifications for development/testing."""

from __future__ import annotations

from database import SessionLocal
from models import Notification, User


def seed():
    db = SessionLocal()
    try:
        # Check if notifications already exist
        existing = db.query(Notification).count()
        if existing > 0:
            print(f"Notifications table already has {existing} rows — skipping seed.")
            return

        # Grab the first user for user-specific notifications
        first_user = db.query(User).first()
        user_id = first_user.id if first_user else None

        notifications = [
            Notification(
                title="Welcome to BlackPapers CRM",
                message="Your CRM is set up and ready to use. Explore contacts, products, and more.",
                type="INFO",
                user_id=None,  # global
            ),
            Notification(
                title="Contact Created",
                message="A new contact John Doe was created.",
                type="SUCCESS",
                user_id=None,  # global
            ),
            Notification(
                title="Product Created",
                message="A new service GST Registration was added.",
                type="SUCCESS",
                user_id=None,  # global
            ),
            Notification(
                title="User Created",
                message="A new employee account was created.",
                type="SUCCESS",
                user_id=user_id,  # user-specific
            ),
            Notification(
                title="System Update",
                message="System configuration updated. Please review the new settings.",
                type="WARNING",
                user_id=None,  # global
            ),
            Notification(
                title="Action Required",
                message="You have pending follow-ups that need attention.",
                type="ERROR",
                user_id=user_id,  # user-specific
            ),
        ]

        db.add_all(notifications)
        db.commit()
        print(f"Seeded {len(notifications)} sample notifications.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
