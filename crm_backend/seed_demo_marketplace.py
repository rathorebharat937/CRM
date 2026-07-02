"""Seed demo API & App Marketplace."""

from database import SessionLocal
from marketplace_config import INTEGRATION_CATALOG
from models import Company, MarketplaceIntegration, MarketplaceSettings, MarketplaceWebhook
from services.marketplace_service import ensure_catalog_rows, generate_webhook_secret, install_integration


def seed_demo_marketplace() -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("No company found. Run seed_company.py first.")
            return

        settings = db.query(MarketplaceSettings).filter(MarketplaceSettings.company_id == company.id).first()
        if not settings:
            settings = MarketplaceSettings(company_id=company.id, is_enabled=True, public_api_enabled=True)
            db.add(settings)
        else:
            settings.is_enabled = True
            settings.public_api_enabled = True

        ensure_catalog_rows(db, company.id)
        db.flush()

        demo_keys = {"razorpay", "whatsapp_business", "google_sheets"}
        for row in db.query(MarketplaceIntegration).filter(MarketplaceIntegration.company_id == company.id).all():
            if row.integration_key in demo_keys and row.status != "installed":
                catalog = next(c for c in INTEGRATION_CATALOG if c["integration_key"] == row.integration_key)
                install_integration(db, row, {f: "demo-configured" for f in catalog["config_fields"][:1]})

        if not db.query(MarketplaceWebhook).filter(MarketplaceWebhook.company_id == company.id).first():
            db.add(
                MarketplaceWebhook(
                    company_id=company.id,
                    name="Deal wins → Slack",
                    endpoint_url="https://hooks.example.com/blackpapers/deals",
                    events_json=["deal.stage_changed", "invoice.issued"],
                    signing_secret=generate_webhook_secret(),
                    status="active",
                )
            )

        db.commit()
        print("API Marketplace enabled with demo integrations and webhook.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_marketplace()
