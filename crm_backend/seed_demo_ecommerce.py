"""Seed demo eCommerce store (Phase 1 MVP)."""

from __future__ import annotations

import argparse
from decimal import Decimal

from database import SessionLocal
from ecommerce_config import normalize_slug, product_online_slug, product_display_image_url
from models import Company, Product, StoreSettings, WebsiteSettings


def seed_demo_ecommerce(reset: bool = False) -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("No company found. Run seed_company.py first.")
            return

        site = db.query(WebsiteSettings).filter(WebsiteSettings.company_id == company.id).first()
        slug = site.company_slug if site else normalize_slug(company.display_name or "blackpapers")

        settings = db.query(StoreSettings).filter(StoreSettings.company_id == company.id).first()
        if not settings:
            settings = StoreSettings(company_id=company.id)
            db.add(settings)
            db.flush()

        if reset:
            settings.is_enabled = False

        settings.is_enabled = True
        settings.store_name = company.display_name
        settings.guest_checkout_allowed = True
        settings.flat_shipping_rate = Decimal("0")
        settings.free_shipping_above = None
        settings.default_payment_method = "bank_transfer"
        settings.auto_create_sales_order = True
        settings.bank_details = (
            "Bank: Kotak Mahindra Bank\n"
            "A/c: BlackPapers Sarthies Private Limited · 1910202300\n"
            "IFSC: KKBK0004599 · UPI: blackpapers@kotak"
        )

        products = (
            db.query(Product)
            .filter(Product.company_id == company.id, Product.status == "active")
            .order_by(Product.id.asc())
            .limit(6)
            .all()
        )
        enabled = 0
        for product in products:
            price = product.offer_price or product.total_price
            if not price or float(price) <= 0:
                product.total_price = Decimal("4999")
                product.offer_price = Decimal("3999")
            product.sell_online = True
            if not product.online_slug:
                product.online_slug = product_online_slug(product)
            if not product.online_description:
                product.online_description = product.description or f"Order {product.name} online."
            if not product.online_image_url:
                product.online_image_url = product_display_image_url(product)
            enabled += 1

        db.commit()
        print(f"eCommerce demo ready — {enabled} products online")
        print(f"  Shop: /s/{slug}/shop")
        print(f"  CRM admin: /ecommerce")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed_demo_ecommerce(reset=args.reset)
