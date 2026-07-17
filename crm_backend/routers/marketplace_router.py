"""API & App Marketplace API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from marketplace_config import INTEGRATION_CATALOG, WEBHOOK_EVENT_TYPES
from marketplace_schemas import (
    IntegrationCatalogItem,
    MarketplaceApiKeyCreateRequest,
    MarketplaceApiKeyCreateResponse,
    MarketplaceApiKeyListItem,
    MarketplaceDashboardResponse,
    MarketplaceInstallRequest,
    MarketplaceIntegrationResponse,
    MarketplaceSettingsResponse,
    MarketplaceSettingsUpdateRequest,
    MarketplaceWebhookCreateRequest,
    MarketplaceWebhookResponse,
)
from tenant_utils import get_current_company
from auth_utils import get_db, require_permission
from models import Company, MarketplaceApiKey, MarketplaceIntegration, MarketplaceSettings, MarketplaceWebhook, User
from services.marketplace_service import (
    ensure_catalog_rows,
    generate_api_key,
    generate_webhook_secret,
    install_integration,
    uninstall_integration,
)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])




def _get_settings(db: Session, company: Company) -> MarketplaceSettings:
    settings = db.query(MarketplaceSettings).filter(MarketplaceSettings.company_id == company.id).first()
    if not settings:
        settings = MarketplaceSettings(company_id=company.id, is_enabled=True)
        db.add(settings)
        db.flush()
    return settings


def _require_enabled(settings: MarketplaceSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="API Marketplace is not enabled")


@router.get("/dashboard", response_model=MarketplaceDashboardResponse)
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_permission("marketplace.view"))):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    ensure_catalog_rows(db, company.id)
    db.commit()
    installed = (
        db.query(func.count(MarketplaceIntegration.id))
        .filter(MarketplaceIntegration.company_id == company.id, MarketplaceIntegration.status == "installed")
        .scalar()
        or 0
    )
    keys = (
        db.query(func.count(MarketplaceApiKey.id))
        .filter(MarketplaceApiKey.company_id == company.id, MarketplaceApiKey.is_active.is_(True))
        .scalar()
        or 0
    )
    hooks = (
        db.query(func.count(MarketplaceWebhook.id))
        .filter(MarketplaceWebhook.company_id == company.id, MarketplaceWebhook.status == "active")
        .scalar()
        or 0
    )
    return MarketplaceDashboardResponse(
        is_enabled=settings.is_enabled,
        installed_count=installed,
        api_key_count=keys,
        active_webhooks=hooks,
    )


@router.get("/settings", response_model=MarketplaceSettingsResponse)
def get_settings(db: Session = Depends(get_db), user: User = Depends(require_permission("marketplace.view"))):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    return MarketplaceSettingsResponse(
        is_enabled=settings.is_enabled,
        public_api_enabled=settings.public_api_enabled,
        max_api_keys=int(settings.max_api_keys or 10),
    )


@router.put("/settings", response_model=MarketplaceSettingsResponse)
def update_settings(
    body: MarketplaceSettingsUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketplace.manage_settings")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    if body.is_enabled is not None:
        settings.is_enabled = body.is_enabled
    if body.public_api_enabled is not None:
        settings.public_api_enabled = body.public_api_enabled
    if body.max_api_keys is not None:
        settings.max_api_keys = body.max_api_keys
    db.commit()
    return MarketplaceSettingsResponse(
        is_enabled=settings.is_enabled,
        public_api_enabled=settings.public_api_enabled,
        max_api_keys=int(settings.max_api_keys or 10),
    )


@router.get("/catalog", response_model=list[IntegrationCatalogItem])
def catalog(db: Session = Depends(get_db), user: User = Depends(require_permission("marketplace.view"))):
    company = get_current_company(db, user)
    ensure_catalog_rows(db, company.id)
    db.commit()
    rows = {r.integration_key: r for r in db.query(MarketplaceIntegration).filter(MarketplaceIntegration.company_id == company.id).all()}
    items = []
    for item in INTEGRATION_CATALOG:
        row = rows.get(item["integration_key"])
        items.append(
            IntegrationCatalogItem(
                integration_key=item["integration_key"],
                name=item["name"],
                category=item["category"],
                description=item["description"],
                config_fields=item["config_fields"],
                status=row.status if row else "available",
                installed=bool(row and row.status == "installed"),
                integration_id=row.id if row else None,
            )
        )
    return items


@router.get("/integrations/{integration_id}", response_model=MarketplaceIntegrationResponse)
def get_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketplace.view")),
):
    company = get_current_company(db, user)
    row = db.query(MarketplaceIntegration).filter(MarketplaceIntegration.id == integration_id, MarketplaceIntegration.company_id == company.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Integration not found")
    return MarketplaceIntegrationResponse(
        id=row.id,
        integration_key=row.integration_key,
        name=row.name,
        category=row.category,
        status=row.status,
        config_json=row.config_json or {},
        installed_at=row.installed_at,
    )


@router.post("/integrations/{integration_id}/install", response_model=MarketplaceIntegrationResponse)
def install(
    integration_id: int,
    body: MarketplaceInstallRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketplace.install")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    row = db.query(MarketplaceIntegration).filter(MarketplaceIntegration.id == integration_id, MarketplaceIntegration.company_id == company.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Integration not found")
    install_integration(db, row, body.config_json)
    db.commit()
    db.refresh(row)
    return MarketplaceIntegrationResponse(
        id=row.id,
        integration_key=row.integration_key,
        name=row.name,
        category=row.category,
        status=row.status,
        config_json=row.config_json or {},
        installed_at=row.installed_at,
    )


@router.post("/integrations/{integration_id}/uninstall", response_model=MarketplaceIntegrationResponse)
def uninstall(
    integration_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketplace.install")),
):
    company = get_current_company(db, user)
    row = db.query(MarketplaceIntegration).filter(MarketplaceIntegration.id == integration_id, MarketplaceIntegration.company_id == company.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Integration not found")
    uninstall_integration(db, row)
    db.commit()
    db.refresh(row)
    return MarketplaceIntegrationResponse(
        id=row.id,
        integration_key=row.integration_key,
        name=row.name,
        category=row.category,
        status=row.status,
        config_json=row.config_json or {},
        installed_at=row.installed_at,
    )


@router.get("/api-keys", response_model=list[MarketplaceApiKeyListItem])
def list_api_keys(db: Session = Depends(get_db), user: User = Depends(require_permission("marketplace.manage_keys"))):
    company = get_current_company(db, user)
    rows = db.query(MarketplaceApiKey).filter(MarketplaceApiKey.company_id == company.id).order_by(MarketplaceApiKey.created_at.desc()).all()
    return [
        MarketplaceApiKeyListItem(
            id=r.id,
            name=r.name,
            key_prefix=r.key_prefix,
            scopes_json=r.scopes_json or [],
            is_active=r.is_active,
            last_used_at=r.last_used_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/api-keys", response_model=MarketplaceApiKeyCreateResponse)
def create_api_key(
    body: MarketplaceApiKeyCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketplace.manage_keys")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    active = db.query(func.count(MarketplaceApiKey.id)).filter(MarketplaceApiKey.company_id == company.id, MarketplaceApiKey.is_active.is_(True)).scalar() or 0
    if active >= int(settings.max_api_keys or 10):
        raise HTTPException(status_code=400, detail="API key limit reached")
    raw, prefix, key_hash = generate_api_key()
    row = MarketplaceApiKey(
        company_id=company.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes_json=body.scopes_json,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return MarketplaceApiKeyCreateResponse(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        api_key=raw,
        scopes_json=row.scopes_json or [],
        created_at=row.created_at,
    )


@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketplace.manage_keys")),
):
    company = get_current_company(db, user)
    row = db.query(MarketplaceApiKey).filter(MarketplaceApiKey.id == key_id, MarketplaceApiKey.company_id == company.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    row.is_active = False
    db.commit()
    return {"ok": True}


@router.get("/webhooks", response_model=list[MarketplaceWebhookResponse])
def list_webhooks(db: Session = Depends(get_db), user: User = Depends(require_permission("marketplace.manage_webhooks"))):
    company = get_current_company(db, user)
    rows = db.query(MarketplaceWebhook).filter(MarketplaceWebhook.company_id == company.id).order_by(MarketplaceWebhook.created_at.desc()).all()
    return [
        MarketplaceWebhookResponse(
            id=r.id,
            name=r.name,
            endpoint_url=r.endpoint_url,
            events_json=r.events_json or [],
            status=r.status,
            integration_id=r.integration_id,
            signing_secret=r.signing_secret,
            last_triggered_at=r.last_triggered_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/webhooks", response_model=MarketplaceWebhookResponse)
def create_webhook(
    body: MarketplaceWebhookCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketplace.manage_webhooks")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    invalid = [e for e in body.events_json if e not in WEBHOOK_EVENT_TYPES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown events: {', '.join(invalid)}")
    row = MarketplaceWebhook(
        company_id=company.id,
        integration_id=body.integration_id,
        name=body.name,
        endpoint_url=body.endpoint_url.strip(),
        events_json=body.events_json,
        signing_secret=generate_webhook_secret(),
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return MarketplaceWebhookResponse(
        id=row.id,
        name=row.name,
        endpoint_url=row.endpoint_url,
        events_json=row.events_json or [],
        status=row.status,
        integration_id=row.integration_id,
        signing_secret=row.signing_secret,
        last_triggered_at=row.last_triggered_at,
        created_at=row.created_at,
    )


@router.get("/webhook-events")
def webhook_events(_: User = Depends(require_permission("marketplace.view"))):
    return WEBHOOK_EVENT_TYPES
