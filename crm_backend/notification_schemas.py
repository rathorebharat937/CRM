from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    type: str = Field(default="INFO", max_length=20)
    user_id: int | None = None


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    user_id: int | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    limit: int


class UnreadCountResponse(BaseModel):
    count: int
