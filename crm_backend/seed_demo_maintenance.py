"""Seed demo Maintenance / CMMS (Phase 1 MVP)."""

from __future__ import annotations

import argparse
from datetime import timedelta

from database import SessionLocal
from models import Company, MaintenanceAsset, MaintenanceAssetCategory, Product
from routers.maintenance_router import _get_settings, _recalc_next_pm, seed_asset_categories


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def seed_demo_maintenance(reset: bool = False) -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("No company found. Run seed_company.py first.")
            return

        settings = _get_settings(db, company)
        settings.is_enabled = True
        settings.default_pm_interval_days = 90
        settings.auto_deduct_spare_parts = True
        settings.notify_roles_json = ["Admin", "Manager"]

        seed_asset_categories(db, company.id)
        db.flush()

        category = (
            db.query(MaintenanceAssetCategory)
            .filter(
                MaintenanceAssetCategory.company_id == company.id,
                MaintenanceAssetCategory.name == "Production machine",
            )
            .first()
        )

        spare = (
            db.query(Product)
            .filter(Product.company_id == company.id, Product.name.ilike("%bearing%"))
            .first()
        )
        if not spare:
            spare = Product(
                company_id=company.id,
                name="Machine bearing kit",
                service_code="SP-BRG-001",
                unit="pcs",
                inventory_tracked=True,
                is_spare_part=True,
                status="active",
                opening_recorded=True,
                on_hand_quantity=10,
            )
            db.add(spare)
            db.flush()
        else:
            spare.is_spare_part = True

        grease = (
            db.query(Product)
            .filter(Product.company_id == company.id, Product.name.ilike("%grease%"))
            .first()
        )
        if not grease:
            grease = Product(
                company_id=company.id,
                name="Industrial grease",
                service_code="SP-GRS-001",
                unit="kg",
                inventory_tracked=True,
                is_spare_part=True,
                status="active",
                opening_recorded=True,
                on_hand_quantity=5,
            )
            db.add(grease)
            db.flush()
        else:
            grease.is_spare_part = True

        asset = (
            db.query(MaintenanceAsset)
            .filter(MaintenanceAsset.company_id == company.id, MaintenanceAsset.asset_code == "AST-DEMO-001")
            .first()
        )
        if not asset:
            today = _utcnow().date()
            asset = MaintenanceAsset(
                company_id=company.id,
                asset_code="AST-DEMO-001",
                name="Soap mixing tank #2",
                category_id=category.id if category else None,
                status="operational",
                criticality="critical",
                location_notes="Shop floor — Line A",
                pm_interval_days=90,
                last_service_date=today - timedelta(days=87),
                notes="Demo asset for Maintenance module",
            )
            _recalc_next_pm(asset, settings)
            db.add(asset)

        db.commit()
        print("Maintenance / CMMS demo ready")
        print("  CRM: /maintenance")
        print("  Demo asset: AST-DEMO-001 — Soap mixing tank #2")
        print("  Spare parts flagged on inventory products")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Maintenance demo data")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed_demo_maintenance(reset=args.reset)
