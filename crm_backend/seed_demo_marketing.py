"""Seed demo Marketing Automation."""

from __future__ import annotations

import argparse

from database import SessionLocal
from marketing_config import CAMPAIGN_TEMPLATES
from models import Company, MarketingCampaign, User
from routers.marketing_router import _get_settings
from services.marketing_service import enroll_audience, generate_campaign_code, process_due_enrollments


def seed_demo_marketing(activate: bool = True) -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("No company found. Run seed_company.py first.")
            return

        settings = _get_settings(db, company)
        settings.is_enabled = True
        db.commit()

        admin = db.query(User).filter(User.role == "Admin").first()
        created = 0
        for tpl in CAMPAIGN_TEMPLATES:
            exists = (
                db.query(MarketingCampaign.id)
                .filter(MarketingCampaign.company_id == company.id, MarketingCampaign.name == tpl["name"])
                .first()
            )
            if exists:
                continue
            campaign = MarketingCampaign(
                company_id=company.id,
                campaign_code=generate_campaign_code(db, company.id),
                name=tpl["name"],
                description=tpl.get("description"),
                campaign_type=tpl["campaign_type"],
                audience_type=tpl["audience_type"],
                audience_filter_json=tpl.get("audience_filter_json", {}),
                steps_json=tpl.get("steps_json", []),
                status="active" if activate else "draft",
                created_by_id=admin.id if admin else None,
            )
            db.add(campaign)
            db.flush()
            if activate:
                enroll_audience(db, campaign, max_enroll=75)
            created += 1
        if activate:
            process_due_enrollments(db, company.id, settings.default_owner_role)
        db.commit()
        print(f"Marketing Automation enabled. Created {created} demo campaign(s).")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Marketing Automation demo data")
    parser.add_argument("--no-activate", action="store_true")
    args = parser.parse_args()
    seed_demo_marketing(activate=not args.no_activate)
