"""AI Assistant API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from ai_assistant_config import DEFAULT_ACTIONS, SUGGESTED_PROMPTS
from ai_assistant_schemas import (
    AiAssistantChatRequest,
    AiAssistantChatResponse,
    AiAssistantMessageResponse,
    AiAssistantSessionListItem,
    AiAssistantSessionListResponse,
    AiAssistantSessionResponse,
    AiAssistantSettingsResponse,
    AiAssistantSettingsUpdateRequest,
)
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import AiAssistantMessage, AiAssistantSession, AiAssistantSettings, Company, User
from services.ai_assistant_service import generate_session_code, process_user_message

router = APIRouter(prefix="/ai-assistant", tags=["ai-assistant"])




def _get_settings(db: Session, company: Company) -> AiAssistantSettings:
    settings = db.query(AiAssistantSettings).filter(AiAssistantSettings.company_id == company.id).first()
    if not settings:
        settings = AiAssistantSettings(company_id=company.id, allowed_actions_json=DEFAULT_ACTIONS, is_enabled=True)
        db.add(settings)
        db.flush()
    return settings


def _require_enabled(settings: AiAssistantSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="AI Assistant is not enabled")


def _msg(m: AiAssistantMessage) -> AiAssistantMessageResponse:
    return AiAssistantMessageResponse(
        id=m.id,
        role=m.role,
        content=m.content,
        intent=m.intent,
        citations_json=m.citations_json or [],
        actions_json=m.actions_json or [],
        created_at=m.created_at,
    )


@router.get("/settings", response_model=AiAssistantSettingsResponse)
def get_settings(db: Session = Depends(get_db), user: User = Depends(require_permission("ai_assistant.view"))):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    actions = settings.allowed_actions_json or DEFAULT_ACTIONS
    return AiAssistantSettingsResponse(
        is_enabled=settings.is_enabled,
        allowed_actions_json=actions,
        retain_sessions_days=int(settings.retain_sessions_days or 90),
        suggested_prompts=SUGGESTED_PROMPTS,
    )


@router.put("/settings", response_model=AiAssistantSettingsResponse)
def update_settings(
    body: AiAssistantSettingsUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ai_assistant.manage_settings")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    if body.is_enabled is not None:
        settings.is_enabled = body.is_enabled
    if body.allowed_actions_json is not None:
        settings.allowed_actions_json = body.allowed_actions_json
    if body.retain_sessions_days is not None:
        settings.retain_sessions_days = body.retain_sessions_days
    db.commit()
    actions = settings.allowed_actions_json or DEFAULT_ACTIONS
    return AiAssistantSettingsResponse(
        is_enabled=settings.is_enabled,
        allowed_actions_json=actions,
        retain_sessions_days=int(settings.retain_sessions_days or 90),
        suggested_prompts=SUGGESTED_PROMPTS,
    )


@router.get("/sessions", response_model=AiAssistantSessionListResponse)
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ai_assistant.view")),
):
    company = get_current_company(db, user)
    rows = (
        db.query(AiAssistantSession)
        .filter(AiAssistantSession.company_id == company.id, AiAssistantSession.user_id == user.id)
        .order_by(AiAssistantSession.updated_at.desc())
        .limit(30)
        .all()
    )
    items = []
    for row in rows:
        count = db.query(AiAssistantMessage).filter(AiAssistantMessage.session_id == row.id).count()
        items.append(
            AiAssistantSessionListItem(
                id=row.id,
                session_code=row.session_code,
                title=row.title,
                message_count=count,
                updated_at=row.updated_at,
            )
        )
    return AiAssistantSessionListResponse(items=items)


@router.get("/sessions/{session_id}", response_model=AiAssistantSessionResponse)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ai_assistant.view")),
):
    company = get_current_company(db, user)
    session = (
        db.query(AiAssistantSession)
        .options(joinedload(AiAssistantSession.messages))
        .filter(
            AiAssistantSession.id == session_id,
            AiAssistantSession.company_id == company.id,
            AiAssistantSession.user_id == user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = sorted(session.messages or [], key=lambda m: m.id)
    return AiAssistantSessionResponse(
        id=session.id,
        session_code=session.session_code,
        title=session.title,
        messages=[_msg(m) for m in messages],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post("/chat", response_model=AiAssistantChatResponse)
def chat(
    body: AiAssistantChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ai_assistant.chat")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    if body.session_id:
        session = (
            db.query(AiAssistantSession)
            .filter(
                AiAssistantSession.id == body.session_id,
                AiAssistantSession.company_id == company.id,
                AiAssistantSession.user_id == user.id,
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = AiAssistantSession(
            company_id=company.id,
            session_code=generate_session_code(db, company.id),
            user_id=user.id,
            title="New chat",
        )
        db.add(session)
        db.flush()

    user_msg = AiAssistantMessage(session_id=session.id, role="user", content=body.message.strip())
    db.add(user_msg)
    db.flush()

    assistant = process_user_message(
        db,
        company_id=company.id,
        user=user,
        session=session,
        message=body.message,
        allowed_actions=settings.allowed_actions_json or DEFAULT_ACTIONS,
    )
    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant)
    db.refresh(session)

    return AiAssistantChatResponse(
        session_id=session.id,
        session_code=session.session_code,
        title=session.title,
        user_message=_msg(user_msg),
        assistant_message=_msg(assistant),
    )
