"""AI Assistant — rule-based helper (no external LLM required)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ai_assistant_config import DEFAULT_ACTIONS, INTENT_KEYWORDS
from models import AiAssistantMessage, AiAssistantSession, Contact, Deal, Invoice, Lead, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_session_code(db: Session, company_id: int) -> str:
    count = db.query(func.count(AiAssistantSession.id)).filter(AiAssistantSession.company_id == company_id).scalar() or 0
    return f"CHAT-{count + 1:04d}"


def detect_intent(message: str, allowed_actions: list[str]) -> str:
    text = message.lower().strip()
    for intent, keywords in INTENT_KEYWORDS.items():
        if intent not in allowed_actions:
            continue
        if any(k in text for k in keywords):
            return intent
    return "search_records" if "search_records" in allowed_actions else allowed_actions[0]


def _search_records(db: Session, company_id: int, user: User, message: str) -> tuple[str, list[dict], list[dict]]:
    term = re.sub(r"(search|find|lookup|show me|list)\s+", "", message.lower()).strip()
    if not term or term in ("leads", "lead", "contacts", "invoices"):
        term = ""

    citations: list[dict] = []
    actions: list[dict] = []
    lines: list[str] = []

    lead_q = db.query(Lead).filter(Lead.company_id == company_id)
    if term:
        like = f"%{term}%"
        lead_q = lead_q.filter(or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.organization_name.ilike(like)))
    if user.role == "Sales":
        lead_q = lead_q.filter(or_(Lead.assigned_to_id == user.id, Lead.assigned_to_id.is_(None)))
    leads = lead_q.order_by(Lead.updated_at.desc().nullslast()).limit(5).all()
    if leads:
        lines.append("**Leads**")
        for lead in leads:
            lines.append(f"- {lead.name} ({lead.status}) — {lead.organization_name or 'No company'}")
            citations.append({"type": "lead", "id": lead.id, "label": lead.name})
            actions.append({"type": "link", "label": "Open lead", "path": f"/leads/{lead.id}"})

    contact_q = db.query(Contact).filter(Contact.company_id == company_id)
    if term:
        like = f"%{term}%"
        contact_q = contact_q.filter(or_(Contact.name.ilike(like), Contact.email.ilike(like)))
    contacts = contact_q.order_by(Contact.name).limit(5).all()
    if contacts:
        lines.append("\n**Contacts**")
        for contact in contacts:
            lines.append(f"- {contact.name} ({contact.contact_type})")
            citations.append({"type": "contact", "id": contact.id, "label": contact.name})
            actions.append({"type": "link", "label": "Open contact", "path": f"/contacts/{contact.id}"})

    if not lines:
        return "I could not find matching records. Try a name, email, or company keyword.", citations, actions
    return "\n".join(lines), citations, actions


def _draft_email(message: str) -> tuple[str, list[dict], list[dict]]:
    subject = "Following up on your enquiry"
    if "payment" in message.lower():
        subject = "Payment reminder — invoice due"
    elif "quote" in message.lower() or "quotation" in message.lower():
        subject = "Your quotation from BlackPapers"
    body = (
        f"Subject: {subject}\n\n"
        "Dear [Client name],\n\n"
        "Thank you for your interest in BlackPapers. "
        "I wanted to follow up on our recent conversation and share the next steps.\n\n"
        "[Add personalised details here]\n\n"
        "Best regards,\n[Your name]\nBlackPapers"
    )
    actions = [{"type": "link", "label": "Email templates", "path": "/admin/email-templates"}]
    return (
        "Here is a draft you can copy into your email client or template editor:\n\n" + body,
        [],
        actions,
    )


def _invoice_help() -> tuple[str, list[dict], list[dict]]:
    text = (
        "To create a GST invoice in BlackPapers:\n\n"
        "1. Open **Invoices** from your app launcher.\n"
        "2. Click **New invoice** (or generate from a confirmed sales order).\n"
        "3. Select the client, add line items, and verify GST %.\n"
        "4. Save as draft, then **Issue** when ready.\n"
        "5. Use **Preview** for the GST layout or share the client link.\n\n"
        "Accountants can record payments from the Payments app once issued."
    )
    actions = [
        {"type": "link", "label": "Open invoices", "path": "/invoices"},
        {"type": "link", "label": "Open payments", "path": "/payments"},
    ]
    return text, [], actions


def _summarize_stats(db: Session, company_id: int) -> tuple[str, list[dict], list[dict]]:
    today = date.today()
    month_start = today.replace(day=1)
    open_leads = db.query(func.count(Lead.id)).filter(Lead.company_id == company_id, Lead.status.in_(["open", "hot", "follow_up", "qualified"])).scalar() or 0
    open_deals = db.query(func.count(Deal.id)).filter(Deal.company_id == company_id, Deal.stage.notin_(["won", "lost"])).scalar() or 0
    month_invoices = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.company_id == company_id, Invoice.issue_date >= month_start)
        .scalar()
        or 0
    )
    now = _utcnow()
    overdue = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(["issued", "partially_paid"]),
            Invoice.due_date < now,
        )
        .scalar()
        or 0
    )
    text = (
        f"**Quick snapshot ({today.strftime('%d %b %Y')})**\n\n"
        f"- Open leads: **{open_leads}**\n"
        f"- Active deals: **{open_deals}**\n"
        f"- Invoices issued this month: **{month_invoices}**\n"
        f"- Overdue invoices: **{overdue}**\n\n"
        "For deeper narrative insights, open **AI Reports** and generate a brief."
    )
    actions = [
        {"type": "link", "label": "AI Reports", "path": "/ai-reports"},
        {"type": "link", "label": "Sales reports", "path": "/sales-reports"},
    ]
    return text, [], actions


def _create_reminder_help() -> tuple[str, list[dict], list[dict]]:
    text = (
        "To set a follow-up reminder:\n\n"
        "1. Open **Follow-ups** from your app launcher.\n"
        "2. Click **New reminder**, pick lead/contact, due date, and notes.\n"
        "3. Assign to yourself or a teammate.\n\n"
        "Marketing campaigns can also auto-create reminders when a drip step runs."
    )
    actions = [{"type": "link", "label": "Open follow-ups", "path": "/follow-ups"}]
    return text, [], actions


def process_user_message(
    db: Session,
    *,
    company_id: int,
    user: User,
    session: AiAssistantSession,
    message: str,
    allowed_actions: list[str] | None = None,
) -> AiAssistantMessage:
    actions_allowed = allowed_actions or DEFAULT_ACTIONS
    intent = detect_intent(message, actions_allowed)

    if intent == "draft_email":
        content, citations, actions = _draft_email(message)
    elif intent == "invoice_help":
        content, citations, actions = _invoice_help()
    elif intent == "summarize_stats":
        content, citations, actions = _summarize_stats(db, company_id)
    elif intent == "create_reminder":
        content, citations, actions = _create_reminder_help()
    else:
        content, citations, actions = _search_records(db, company_id, user, message)

    assistant = AiAssistantMessage(
        session_id=session.id,
        role="assistant",
        content=content,
        intent=intent,
        citations_json=citations,
        actions_json=actions,
    )
    db.add(assistant)
    session.updated_at = _utcnow()
    if session.title == "New chat" and len(message) > 0:
        session.title = message[:60] + ("…" if len(message) > 60 else "")
    return assistant
