"""Seed demo Subscription Management (Phase 1 MVP)."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from database import SessionLocal
from models import Company, Contact, CustomerSubscription, SubscriptionPlan
from routers.subscriptions_router import _get_settings
from services.subscription_service import initialize_subscription_dates


def seed_demo_subscriptions(reset: bool = False) -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("No company found. Run seed_company.py first.")
            return

        settings = _get_settings(db, company)
        settings.is_enabled = True
        settings.subscription_prefix = "SUB"
        settings.default_reminder_days = [7, 3, 1]
        settings.auto_invoice_mode = "draft"
        settings.notify_roles_json = ["Admin", "Manager", "Accountant"]

        contacts = db.query(Contact).filter(Contact.company_id == company.id).limit(3).all()
        if not contacts:
            print("No contact found. Run seed_clients.py first.")
            return

        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.company_id == company.id, SubscriptionPlan.plan_code == "AMC-GOLD")
            .first()
        )
        if not plan:
            plan = SubscriptionPlan(
                company_id=company.id,
                plan_code="AMC-GOLD",
                name="Annual AMC — Gold",
                description="Yearly maintenance contract — demo plan",
                billing_interval="yearly",
                price=24000,
                currency="INR",
                gst_rate=18,
                trial_days=0,
                status="active",
                sort_order=1,
            )
            db.add(plan)
            db.flush()

        monthly = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.company_id == company.id, SubscriptionPlan.plan_code == "SVC-MONTHLY")
            .first()
        )
        if not monthly:
            monthly = SubscriptionPlan(
                company_id=company.id,
                plan_code="SVC-MONTHLY",
                name="Monthly Service Retainer",
                description="Monthly recurring service fee",
                billing_interval="monthly",
                price=5000,
                currency="INR",
                gst_rate=18,
                status="active",
                sort_order=2,
            )
            db.add(monthly)
            db.flush()

        demo_subs = [
            ("SUB-DEMO-001", contacts[0], monthly, date.today() - timedelta(days=30), "active"),
            ("SUB-DEMO-002", contacts[1] if len(contacts) > 1 else contacts[0], plan, date.today() - timedelta(days=180), "active"),
        ]
        created = 0
        for number, contact, chosen_plan, start, status in demo_subs:
            exists = (
                db.query(CustomerSubscription.id)
                .filter(
                    CustomerSubscription.company_id == company.id,
                    CustomerSubscription.subscription_number == number,
                )
                .first()
            )
            if exists:
                continue
            sub = CustomerSubscription(
                company_id=company.id,
                subscription_number=number,
                contact_id=contact.id,
                plan_id=chosen_plan.id,
                quantity=1,
                status=status,
                notes="Level 5 subscription demo",
            )
            initialize_subscription_dates(sub, chosen_plan, start)
            db.add(sub)
            created += 1

        db.commit()
        print("Subscriptions demo ready")
        print("  CRM: /subscriptions")
        print(f"  Plans: {plan.plan_code}, {monthly.plan_code}")
        print(f"  Demo subscribers created: {created}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Subscriptions demo data")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed_demo_subscriptions(reset=args.reset)
