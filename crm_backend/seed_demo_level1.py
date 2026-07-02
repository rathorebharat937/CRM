"""Seed demo in-app notifications for Level 1."""

from __future__ import annotations

from database import SessionLocal
from models import Company, Notification, User


DEMO_NOTIFICATIONS_BY_ROLE = {
    "Accountant": [
        ("payment", "Payment due", "3 client invoices are overdue for collection.", "/payments"),
        ("approval", "Bills to approve", "2 vendor bills are waiting for your review.", "/vendor-bills"),
        ("approval", "Expense claims", "Expense reimbursements need approval.", "/expenses"),
        ("task", "GST filing reminder", "Monthly GST summary is ready to review.", "/tax-reports"),
        ("system", "Finance alerts active", "You will see payment, approval, and tax reminders here.", "/profile"),
    ],
    "Sales": [
        ("follow_up", "Follow-up due today", "Call Acme Corp about pending quotation.", "/follow-ups"),
        ("approval", "Quote awaiting send", "Your draft quotation is ready to send to the client.", "/quotations"),
        ("payment", "Deal update", "Client viewed the shared quotation link.", "/pipeline"),
        ("task", "Task deadline", "You have project tasks due this week.", "/projects/my-tasks"),
        ("system", "Sales alerts active", "Follow-ups, quotes, and client activity will appear here.", "/profile"),
    ],
}

DEFAULT_DEMO_NOTIFICATIONS = [
    ("follow_up", "Follow-up due today", "Call Acme Corp about pending quotation.", "/follow-ups"),
    ("approval", "Approval pending", "2 quotations are waiting for your review.", "/approvals"),
    ("payment", "Payment reminder", "Invoice outstanding balance needs collection follow-up.", "/payments"),
    ("task", "Task deadline", "You have project tasks due this week.", "/projects/my-tasks"),
    ("system", "Welcome to BlackPapers CRM", "Your notification centre is active. Demo alerts are shown until live email/SMS is configured.", "/profile"),
]


def _notifications_for_role(role: str) -> list[tuple[str, str, str, str]]:
    return DEMO_NOTIFICATIONS_BY_ROLE.get(role, DEFAULT_DEMO_NOTIFICATIONS)


def _demo_titles_for_role(role: str) -> set[str]:
    return {title for _, title, _, _ in _notifications_for_role(role)}


def seed(reset: bool = False) -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("SKIP demo notifications — no company")
            return

        if reset:
            deleted = db.query(Notification).filter(Notification.company_id == company.id).delete()
            print(f"RESET removed {deleted} notifications")

        staff = (
            db.query(User)
            .filter(User.status == "active", User.role != "User")
            .all()
        )
        if not staff:
            print("SKIP demo notifications — no staff users")
            return

        created = 0
        for user in staff:
            if user.company_id is None:
                user.company_id = company.id

            demo_set = _notifications_for_role(user.role)
            demo_titles = _demo_titles_for_role(user.role)

            if not reset:
                existing_titles = {
                    row[0]
                    for row in db.query(Notification.title)
                    .filter(
                        Notification.user_id == user.id,
                        Notification.title.in_(demo_titles),
                    )
                    .all()
                }
                demo_set = [
                    item for item in demo_set if item[1] not in existing_titles
                ]
                if not demo_set:
                    continue

            for category, title, message, link in demo_set:
                db.add(
                    Notification(
                        company_id=company.id,
                        user_id=user.id,
                        category=category,
                        title=title,
                        message=message,
                        link_path=link,
                        is_read=False,
                    )
                )
                created += 1
        db.commit()
        print(f"Demo notifications seed complete ({created} rows).")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all company notifications, then re-seed demo alerts",
    )
    args = parser.parse_args()
    seed(reset=args.reset)
