"""Pydantic schemas for Marketing Automation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MarketingSettingsResponse(BaseModel):
    is_enabled: bool
    default_owner_role: str
    max_active_campaigns: int


class MarketingSettingsUpdateRequest(BaseModel):
    is_enabled: bool | None = None
    default_owner_role: str | None = None
    max_active_campaigns: int | None = None


class CampaignStep(BaseModel):
    delay_days: int = 0
    channel: str = "reminder"
    subject: str
    body: str


class MarketingCampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    campaign_type: str = "drip"
    audience_type: str = "leads"
    audience_filter_json: dict[str, Any] = Field(default_factory=dict)
    steps_json: list[CampaignStep] = Field(default_factory=list)


class MarketingCampaignUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    campaign_type: str | None = None
    audience_type: str | None = None
    audience_filter_json: dict[str, Any] | None = None
    steps_json: list[CampaignStep] | None = None


class MarketingCampaignListItem(BaseModel):
    id: int
    campaign_code: str
    name: str
    campaign_type: str
    status: str
    audience_type: str
    enrolled_count: int
    sent_count: int
    step_count: int
    activated_at: datetime | None
    created_at: datetime | None


class MarketingCampaignListResponse(BaseModel):
    items: list[MarketingCampaignListItem]
    total: int


class MarketingCampaignResponse(BaseModel):
    id: int
    campaign_code: str
    name: str
    description: str | None
    campaign_type: str
    status: str
    audience_type: str
    audience_filter_json: dict[str, Any]
    steps_json: list[dict[str, Any]]
    enrolled_count: int
    sent_count: int
    activated_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class MarketingDashboardResponse(BaseModel):
    is_enabled: bool
    active_campaigns: int
    total_enrolled: int
    sends_today: int
    due_now: int


class MarketingEnrollmentItem(BaseModel):
    id: int
    lead_id: int | None
    contact_id: int | None
    lead_name: str | None
    contact_name: str | None
    status: str
    current_step: int
    next_send_at: datetime | None
    enrolled_at: datetime | None


class MarketingSendLogItem(BaseModel):
    id: int
    step_index: int
    channel: str
    status: str
    subject: str | None
    body_preview: str | None
    sent_at: datetime | None


class MarketingTemplateResponse(BaseModel):
    key: str
    name: str
    campaign_type: str
    audience_type: str
    description: str | None
    steps_json: list[dict[str, Any]]
