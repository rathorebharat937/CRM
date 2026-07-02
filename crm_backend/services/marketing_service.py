"""Marketing Automation business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from marketing_config import CAMPAIGN_STATUSES, CAMPAIGN_TYPES, DEFAULT_CAMPAIGN_PREFIX, ENROLLMENT_STATUSES
from models import Contact, FollowUpReminder, Lead, MarketingCampaign, MarketingEnrollment, MarketingSendLog, User
from services.notification_service import notify_user


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_campaign_code(db: Session, company_id: int) -> str:
    codes = (
        db.query(MarketingCampaign.campaign_code)
        .filter(MarketingCampaign.company_id == company_id)
        .all()
    )
    max_n = 0
    prefix = f"{DEFAULT_CAMPAIGN_PREFIX}-"
    for (code,) in codes:
        if code and code.startswith(prefix):
            try:
                max_n = max(max_n, int(code.rsplit("-", 1)[-1]))
            except ValueError:
                continue
    return f"{DEFAULT_CAMPAIGN_PREFIX}-{max_n + 1:04d}"


def _match_lead(lead: Lead, filters: dict) -> bool:
    statuses = filters.get("lead_status") or []
    if statuses and lead.status not in statuses:
        return False
    sources = filters.get("lead_source") or []
    if sources and lead.source not in sources:
        return False
    return True


def _match_contact(contact: Contact, filters: dict) -> bool:
    types = filters.get("contact_type") or []
    if types and contact.contact_type not in types:
        return False
    return True


def enroll_audience(db: Session, campaign: MarketingCampaign, max_enroll: int | None = None) -> int:
    filters = campaign.audience_filter_json or {}
    created = 0
    now = _utcnow()
    steps = campaign.steps_json or []
    first_delay = int(steps[0].get("delay_days", 0)) if steps else 0
    next_send = now + timedelta(days=first_delay)

    existing_leads = {
        row[0]
        for row in db.query(MarketingEnrollment.lead_id)
        .filter(MarketingEnrollment.campaign_id == campaign.id, MarketingEnrollment.lead_id.isnot(None))
        .all()
    }
    existing_contacts = {
        row[0]
        for row in db.query(MarketingEnrollment.contact_id)
        .filter(MarketingEnrollment.campaign_id == campaign.id, MarketingEnrollment.contact_id.isnot(None))
        .all()
    }

    if campaign.audience_type in ("leads", "both"):
        leads = db.query(Lead).filter(Lead.company_id == campaign.company_id).order_by(Lead.id).all()
        for lead in leads:
            if max_enroll is not None and created >= max_enroll:
                break
            if not _match_lead(lead, filters):
                continue
            if lead.id in existing_leads:
                continue
            db.add(
                MarketingEnrollment(
                    company_id=campaign.company_id,
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    status="active",
                    current_step=0,
                    next_send_at=next_send,
                )
            )
            existing_leads.add(lead.id)
            created += 1

    if campaign.audience_type in ("contacts", "both"):
        contacts = db.query(Contact).filter(Contact.company_id == campaign.company_id).order_by(Contact.id).all()
        for contact in contacts:
            if max_enroll is not None and created >= max_enroll:
                break
            if not _match_contact(contact, filters):
                continue
            if contact.id in existing_contacts:
                continue
            db.add(
                MarketingEnrollment(
                    company_id=campaign.company_id,
                    campaign_id=campaign.id,
                    contact_id=contact.id,
                    status="active",
                    current_step=0,
                    next_send_at=next_send,
                )
            )
            existing_contacts.add(contact.id)
            created += 1

    campaign.enrolled_count = int(campaign.enrolled_count or 0) + created
    return created


def _owner_user(db: Session, company_id: int, lead: Lead | None, default_role: str) -> User | None:
    if lead and lead.assigned_to_id:
        user = db.query(User).filter(User.id == lead.assigned_to_id, User.status == "active").first()
        if user:
            return user
    return (
        db.query(User)
        .filter(User.company_id == company_id, User.role == default_role, User.status == "active")
        .order_by(User.id)
        .first()
    )


def _execute_step(
    db: Session,
    *,
    enrollment: MarketingEnrollment,
    campaign: MarketingCampaign,
    step: dict,
    step_index: int,
    default_role: str,
) -> MarketingSendLog:
    channel = step.get("channel", "reminder")
    subject = step.get("subject") or campaign.name
    body = step.get("body") or ""
    lead = enrollment.lead
    contact = enrollment.contact
    owner = _owner_user(db, campaign.company_id, lead, default_role)
    linked_type = None
    linked_id = None
    status = "sent"

    if channel == "reminder" and owner:
        due = _utcnow() + timedelta(days=1)
        reminder = FollowUpReminder(
            company_id=campaign.company_id,
            assigned_to_id=owner.id,
            created_by_id=owner.id,
            reminder_type="call",
            priority="normal",
            status="pending",
            title=subject,
            notes=body,
            due_at=due,
            lead_id=enrollment.lead_id,
            contact_id=enrollment.contact_id,
        )
        db.add(reminder)
        db.flush()
        linked_type = "follow_up_reminder"
        linked_id = reminder.id
    elif channel == "in_app" and owner:
        notify_user(
            db,
            company_id=campaign.company_id,
            user_id=owner.id,
            category="marketing",
            title=subject,
            message=body,
            link_path="/leads" if enrollment.lead_id else "/contacts",
        )
        linked_type = "notification"
    elif channel == "email_draft":
        status = "skipped"
        body = f"[Email draft — connect SMTP to send]\n\nSubject: {subject}\n\n{body}"

    log = MarketingSendLog(
        enrollment_id=enrollment.id,
        step_index=step_index,
        channel=channel,
        status=status,
        subject=subject,
        body_preview=body[:500],
        linked_record_type=linked_type,
        linked_record_id=linked_id,
    )
    db.add(log)
    campaign.sent_count = int(campaign.sent_count or 0) + 1
    return log


def process_due_enrollments(db: Session, company_id: int, default_role: str = "Sales") -> int:
    now = _utcnow()
    due = (
        db.query(MarketingEnrollment)
        .join(MarketingCampaign)
        .filter(
            MarketingEnrollment.company_id == company_id,
            MarketingEnrollment.status == "active",
            MarketingEnrollment.next_send_at <= now,
            MarketingCampaign.status == "active",
        )
        .all()
    )
    processed = 0
    for enrollment in due:
        campaign = enrollment.campaign
        steps = campaign.steps_json or []
        step_index = int(enrollment.current_step or 0)
        if step_index >= len(steps):
            enrollment.status = "completed"
            enrollment.completed_at = now
            enrollment.next_send_at = None
            continue
        step = steps[step_index]
        _execute_step(
            db,
            enrollment=enrollment,
            campaign=campaign,
            step=step,
            step_index=step_index,
            default_role=default_role,
        )
        enrollment.current_step = step_index + 1
        if enrollment.current_step >= len(steps):
            enrollment.status = "completed"
            enrollment.completed_at = now
            enrollment.next_send_at = None
        else:
            next_step = steps[enrollment.current_step]
            enrollment.next_send_at = now + timedelta(days=int(next_step.get("delay_days", 0)))
        processed += 1
    return processed


def validate_campaign_type(value: str) -> None:
    if value not in CAMPAIGN_TYPES:
        raise ValueError(f"campaign_type must be one of: {', '.join(CAMPAIGN_TYPES)}")


def validate_campaign_status(value: str) -> None:
    if value not in CAMPAIGN_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(CAMPAIGN_STATUSES)}")
