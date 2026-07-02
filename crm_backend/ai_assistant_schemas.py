"""Pydantic schemas for AI Assistant."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AiAssistantSettingsResponse(BaseModel):
    is_enabled: bool
    allowed_actions_json: list[str]
    retain_sessions_days: int
    suggested_prompts: list[str]


class AiAssistantSettingsUpdateRequest(BaseModel):
    is_enabled: bool | None = None
    allowed_actions_json: list[str] | None = None
    retain_sessions_days: int | None = None


class AiAssistantSessionListItem(BaseModel):
    id: int
    session_code: str
    title: str
    message_count: int
    updated_at: datetime | None


class AiAssistantSessionListResponse(BaseModel):
    items: list[AiAssistantSessionListItem]


class AiAssistantMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    intent: str | None
    citations_json: list[dict[str, Any]]
    actions_json: list[dict[str, Any]]
    created_at: datetime | None


class AiAssistantSessionResponse(BaseModel):
    id: int
    session_code: str
    title: str
    messages: list[AiAssistantMessageResponse]
    created_at: datetime | None
    updated_at: datetime | None


class AiAssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: int | None = None


class AiAssistantChatResponse(BaseModel):
    session_id: int
    session_code: str
    title: str
    user_message: AiAssistantMessageResponse
    assistant_message: AiAssistantMessageResponse
