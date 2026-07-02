"""Enable all Level 5 platform modules for the demo company."""

from __future__ import annotations

from database import SessionLocal
from models import (
    AiAssistantSettings,
    AiReportSettings,
    Company,
    FieldServiceSettings,
    MaintenanceSettings,
    ManufacturingSettings,
    MarketingSettings,
    MarketplaceSettings,
    PosSettings,
    QualitySettings,
    RentalSettings,
    StoreSettings,
    SubscriptionSettings,
    WorkflowSettings,
)
from routers.ai_assistant_router import _get_settings as get_ai_assistant_settings
from routers.ai_reports_router import _get_settings as get_ai_reports_settings
from routers.field_service_router import _get_settings as get_field_service_settings
from routers.maintenance_router import _get_settings as get_maintenance_settings
from routers.manufacturing_router import _get_settings as get_manufacturing_settings
from routers.marketing_router import _get_settings as get_marketing_settings
from routers.marketplace_router import _get_settings as get_marketplace_settings
from routers.pos_router import _get_settings as get_pos_settings
from routers.rental_router import _get_settings as get_rental_settings
from routers.subscriptions_router import _get_settings as get_subscription_settings
from routers.workflow_router import _get_settings as get_workflow_settings
from services.quality_service import get_quality_settings


def enable_level5_modules() -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("No company found. Run seed_company.py first.")
            return

        getters = [
            get_subscription_settings,
            get_pos_settings,
            get_manufacturing_settings,
            get_maintenance_settings,
            get_field_service_settings,
            get_rental_settings,
            get_ai_reports_settings,
            get_workflow_settings,
            get_marketing_settings,
            get_ai_assistant_settings,
            get_marketplace_settings,
        ]

        enabled = 0
        for getter in getters:
            settings = getter(db, company)
            if not settings.is_enabled:
                settings.is_enabled = True
                enabled += 1

        quality = get_quality_settings(db, company)
        if not quality.is_enabled:
            quality.is_enabled = True
            enabled += 1

        store = db.query(StoreSettings).filter(StoreSettings.company_id == company.id).first()
        if store:
            if not store.is_enabled:
                store.is_enabled = True
                enabled += 1
        else:
            db.add(StoreSettings(company_id=company.id, store_name=company.display_name, is_enabled=True))
            enabled += 1

        db.commit()
        print(f"Level 5 modules enabled ({enabled} setting row(s) updated).")
        print("Log out and log back in if app tiles look stale.")
    finally:
        db.close()


if __name__ == "__main__":
    enable_level5_modules()
