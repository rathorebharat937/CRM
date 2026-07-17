from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from chat_config import CHAT_CHANNEL_LABELS, CHAT_CHANNELS, MAX_MESSAGE_LENGTH
from models import ChatMessage, Company, Project, User
from schemas import ChatMessageCreateRequest, ChatMessageListResponse, ChatMessageResponse, ChatMetaResponse, EmployeeOption

router = APIRouter(prefix="/chat", tags=["chat"])




def _msg_resp(msg: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=msg.id,
        sender_id=msg.sender_id,
        sender_name=msg.sender.name if msg.sender else None,
        channel=msg.channel,
        channel_label=CHAT_CHANNEL_LABELS.get(msg.channel, msg.channel),
        recipient_id=msg.recipient_id,
        recipient_name=msg.recipient.name if msg.recipient else None,
        project_id=msg.project_id,
        project_name=msg.project.name if msg.project else None,
        body=msg.body,
        created_at=msg.created_at,
    )


@router.get("/meta", response_model=ChatMetaResponse)
def chat_meta(_: User = Depends(require_permission("chat.view"))):
    return ChatMetaResponse(
        channels=[EmployeeOption(value=k, label=v) for k, v in CHAT_CHANNEL_LABELS.items()],
    )


@router.get("/messages", response_model=ChatMessageListResponse)
def list_messages(
    channel: str = Query("general"),
    project_id: int | None = None,
    recipient_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("chat.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    if channel not in CHAT_CHANNELS:
        raise HTTPException(status_code=400, detail="Invalid channel")

    query = (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.recipient),
            joinedload(ChatMessage.project),
        )
        .filter(ChatMessage.company_id == company.id, ChatMessage.channel == channel)
    )
    if channel == "project" and project_id:
        query = query.filter(ChatMessage.project_id == project_id)
    if channel == "direct" and recipient_id:
        query = query.filter(
            ((ChatMessage.sender_id == recipient_id) | (ChatMessage.recipient_id == recipient_id))
        )

    items = query.order_by(ChatMessage.created_at.desc()).limit(limit).all()
    items.reverse()
    return ChatMessageListResponse(items=[_msg_resp(m) for m in items], total=len(items))


@router.post("/messages", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("chat.send")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    if payload.channel not in CHAT_CHANNELS:
        raise HTTPException(status_code=400, detail="Invalid channel")
    body = (payload.body or "").strip()
    if not body or len(body) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail=f"Message must be 1–{MAX_MESSAGE_LENGTH} characters")

    if payload.channel == "direct" and not payload.recipient_id:
        raise HTTPException(status_code=400, detail="Direct messages require a recipient")
    if payload.channel == "project":
        if not payload.project_id:
            raise HTTPException(status_code=400, detail="Project channel requires a project")
        project = db.query(Project).filter(Project.id == payload.project_id, Project.company_id == company.id).first()
        if not project:
            raise HTTPException(status_code=400, detail="Invalid project")

    msg = ChatMessage(
        company_id=company.id,
        sender_id=current_user.id,
        channel=payload.channel,
        recipient_id=payload.recipient_id,
        project_id=payload.project_id,
        body=body,
    )
    db.add(msg)
    db.commit()
    msg = (
        db.query(ChatMessage)
        .options(joinedload(ChatMessage.sender), joinedload(ChatMessage.recipient), joinedload(ChatMessage.project))
        .filter(ChatMessage.id == msg.id)
        .first()
    )
    log_activity(db, action="chat_message_sent", user_id=current_user.id, email=current_user.email,
                 details=f"Chat message in {payload.channel}", ip_address=get_client_ip(request))
    return _msg_resp(msg)
