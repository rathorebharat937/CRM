"""Pydantic schemas for API & App Marketplace."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class MarketplaceSettingsResponse(BaseModel):
    is_enabled: bool
    public_api_enabled: bool
    max_api_keys: int


class MarketplaceSettingsUpdateRequest(BaseModel):
    is_enabled: bool | None = None
    public_api_enabled: bool | None = None
    max_api_keys: int | None = None


class IntegrationCatalogItem(BaseModel):
    integration_key: str
    name: str
    category: str
    description: str
    config_fields: list[str]
    status: str
    installed: bool
    integration_id: int | None = None


class MarketplaceDashboardResponse(BaseModel):
    is_enabled: bool
    installed_count: int
    api_key_count: int
    active_webhooks: int


class MarketplaceIntegrationResponse(BaseModel):
    id: int
    integration_key: str
    name: str
    category: str
    status: str
    config_json: dict[str, Any]
    installed_at: datetime | None


class MarketplaceInstallRequest(BaseModel):
    config_json: dict[str, Any] = Field(default_factory=dict)


class MarketplaceApiKeyListItem(BaseModel):
    id: int
    name: str
    key_prefix: str
    scopes_json: list[str]
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime | None


class MarketplaceApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes_json: list[str] = Field(default_factory=list)


class MarketplaceApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    api_key: str
    scopes_json: list[str]
    created_at: datetime | None


class MarketplaceWebhookCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    endpoint_url: str
    events_json: list[str] = Field(default_factory=list)
    integration_id: int | None = None


class MarketplaceWebhookResponse(BaseModel):
    id: int
    name: str
    endpoint_url: str
    events_json: list[str]
    status: str
    integration_id: int | None
    signing_secret: str | None
    last_triggered_at: datetime | None
    created_at: datetime | None
