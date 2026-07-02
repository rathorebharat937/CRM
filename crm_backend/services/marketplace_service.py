"""API & App Marketplace business logic."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from marketplace_config import INTEGRATION_CATALOG, INTEGRATION_STATUSES
from models import MarketplaceApiKey, MarketplaceIntegration, MarketplaceWebhook


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    raw = f"bp_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    return raw, prefix, hash_api_key(raw)


def ensure_catalog_rows(db: Session, company_id: int) -> None:
    for item in INTEGRATION_CATALOG:
        exists = (
            db.query(MarketplaceIntegration.id)
            .filter(
                MarketplaceIntegration.company_id == company_id,
                MarketplaceIntegration.integration_key == item["integration_key"],
            )
            .first()
        )
        if exists:
            continue
        db.add(
            MarketplaceIntegration(
                company_id=company_id,
                integration_key=item["integration_key"],
                name=item["name"],
                category=item["category"],
                status="available",
                config_json={},
            )
        )


def install_integration(db: Session, row: MarketplaceIntegration, config_json: dict) -> MarketplaceIntegration:
    row.status = "installed"
    row.config_json = config_json or {}
    row.installed_at = _utcnow()
    return row


def uninstall_integration(db: Session, row: MarketplaceIntegration) -> MarketplaceIntegration:
    row.status = "available"
    row.config_json = {}
    row.installed_at = None
    return row


def generate_webhook_secret() -> str:
    return secrets.token_hex(16)
