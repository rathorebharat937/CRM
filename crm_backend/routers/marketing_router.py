"""Marketing Automation API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from auth_utils import get_client_ip, get_db, require_permission
from marketing_config import CAMPAIGN_TEMPLATES, CAMPAIGN_TYPE_LABELS
from marketing_schemas import (
    MarketingCampaignCreateRequest,
    MarketingCampaignListItem,
    MarketingCampaignListResponse,
    MarketingCampaignResponse,
    MarketingCampaignUpdateRequest,
    MarketingDashboardResponse,
    MarketingEnrollmentItem,
    MarketingSendLogItem,
    MarketingSettingsResponse,
    MarketingSettingsUpdateRequest,
    MarketingTemplateResponse,
)
from models import (
    Company,
    MarketingCampaign,
    MarketingEnrollment,
    MarketingSendLog,
    MarketingSettings,
    User,
)
from services.marketing_service import (
    enroll_audience,
    generate_campaign_code,
    process_due_enrollments,
    validate_campaign_type,
)

router = APIRouter(prefix="/marketing", tags=["marketing"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_company(db: Session) -> Company:
    company = db.query(Company).first()
    if not company:
        raise HTTPException(status_code=400, detail="Company must be configured")
    return company


def _get_settings(db: Session, company: Company) -> MarketingSettings:
    settings = db.query(MarketingSettings).filter(MarketingSettings.company_id == company.id).first()
    if not settings:
        settings = MarketingSettings(company_id=company.id, is_enabled=True)
        db.add(settings)
        db.flush()
    return settings


def _require_enabled(settings: MarketingSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="Marketing Automation is not enabled")


def _campaign_response(c: MarketingCampaign) -> MarketingCampaignResponse:
    return MarketingCampaignResponse(
        id=c.id,
        campaign_code=c.campaign_code,
        name=c.name,
        description=c.description,
        campaign_type=c.campaign_type,
        status=c.status,
        audience_type=c.audience_type,
        audience_filter_json=c.audience_filter_json or {},
        steps_json=c.steps_json or [],
        enrolled_count=int(c.enrolled_count or 0),
        sent_count=int(c.sent_count or 0),
        activated_at=c.activated_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/dashboard", response_model=MarketingDashboardResponse)
def marketing_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    sends_today = (
        db.query(func.count(MarketingSendLog.id))
        .join(MarketingEnrollment)
        .filter(MarketingEnrollment.company_id == company.id, MarketingSendLog.sent_at >= today_start)
        .scalar()
        or 0
    )
    due_now = (
        db.query(func.count(MarketingEnrollment.id))
        .filter(
            MarketingEnrollment.company_id == company.id,
            MarketingEnrollment.status == "active",
            MarketingEnrollment.next_send_at <= _utcnow(),
        )
        .scalar()
        or 0
    )
    active = (
        db.query(func.count(MarketingCampaign.id))
        .filter(MarketingCampaign.company_id == company.id, MarketingCampaign.status == "active")
        .scalar()
        or 0
    )
    enrolled = (
        db.query(func.count(MarketingEnrollment.id))
        .filter(MarketingEnrollment.company_id == company.id, MarketingEnrollment.status == "active")
        .scalar()
        or 0
    )
    return MarketingDashboardResponse(
        is_enabled=settings.is_enabled,
        active_campaigns=active,
        total_enrolled=enrolled,
        sends_today=sends_today,
        due_now=due_now,
    )


@router.get("/settings", response_model=MarketingSettingsResponse)
def get_settings(db: Session = Depends(get_db), _: User = Depends(require_permission("marketing.view"))):
    company = _get_company(db)
    settings = _get_settings(db, company)
    return MarketingSettingsResponse(
        is_enabled=settings.is_enabled,
        default_owner_role=settings.default_owner_role,
        max_active_campaigns=int(settings.max_active_campaigns or 20),
    )


@router.put("/settings", response_model=MarketingSettingsResponse)
def update_settings(
    body: MarketingSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketing.manage_settings")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    if body.is_enabled is not None:
        settings.is_enabled = body.is_enabled
    if body.default_owner_role is not None:
        settings.default_owner_role = body.default_owner_role
    if body.max_active_campaigns is not None:
        settings.max_active_campaigns = body.max_active_campaigns
    db.commit()
    db.commit()
    return MarketingSettingsResponse(
        is_enabled=settings.is_enabled,
        default_owner_role=settings.default_owner_role,
        max_active_campaigns=int(settings.max_active_campaigns or 20),
    )


@router.get("/templates", response_model=list[MarketingTemplateResponse])
def list_templates(_: User = Depends(require_permission("marketing.view"))):
    return [
        MarketingTemplateResponse(
            key=f"tpl-{i}",
            name=t["name"],
            campaign_type=t["campaign_type"],
            audience_type=t["audience_type"],
            description=t.get("description"),
            steps_json=t.get("steps_json", []),
        )
        for i, t in enumerate(CAMPAIGN_TEMPLATES)
    ]


@router.post("/templates/{key}", response_model=MarketingCampaignResponse)
def create_from_template(
    key: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketing.create")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))
    try:
        idx = int(key.replace("tpl-", ""))
        tpl = CAMPAIGN_TEMPLATES[idx]
    except (ValueError, IndexError):
        raise HTTPException(status_code=404, detail="Template not found")
    campaign = MarketingCampaign(
        company_id=company.id,
        campaign_code=generate_campaign_code(db, company.id),
        name=tpl["name"],
        description=tpl.get("description"),
        campaign_type=tpl["campaign_type"],
        audience_type=tpl["audience_type"],
        audience_filter_json=tpl.get("audience_filter_json", {}),
        steps_json=tpl.get("steps_json", []),
        created_by_id=user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    db.commit()
    return _campaign_response(campaign)


@router.get("/campaigns", response_model=MarketingCampaignListResponse)
def list_campaigns(
    db: Session = Depends(get_db),
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require_permission("marketing.view")),
):
    company = _get_company(db)
    q = db.query(MarketingCampaign).filter(MarketingCampaign.company_id == company.id)
    if status:
        q = q.filter(MarketingCampaign.status == status)
    total = q.count()
    rows = q.order_by(MarketingCampaign.updated_at.desc()).limit(limit).all()
    items = [
        MarketingCampaignListItem(
            id=c.id,
            campaign_code=c.campaign_code,
            name=c.name,
            campaign_type=c.campaign_type,
            status=c.status,
            audience_type=c.audience_type,
            enrolled_count=int(c.enrolled_count or 0),
            sent_count=int(c.sent_count or 0),
            step_count=len(c.steps_json or []),
            activated_at=c.activated_at,
            created_at=c.created_at,
        )
        for c in rows
    ]
    return MarketingCampaignListResponse(items=items, total=total)


@router.post("/campaigns", response_model=MarketingCampaignResponse)
def create_campaign(
    body: MarketingCampaignCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketing.create")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))
    try:
        validate_campaign_type(body.campaign_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    campaign = MarketingCampaign(
        company_id=company.id,
        campaign_code=generate_campaign_code(db, company.id),
        name=body.name,
        description=body.description,
        campaign_type=body.campaign_type,
        audience_type=body.audience_type,
        audience_filter_json=body.audience_filter_json,
        steps_json=[s.model_dump() for s in body.steps_json],
        created_by_id=user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    db.commit()
    return _campaign_response(campaign)


@router.get("/campaigns/{campaign_id}", response_model=MarketingCampaignResponse)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketing.view")),
):
    company = _get_company(db)
    campaign = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id, MarketingCampaign.company_id == company.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _campaign_response(campaign)


@router.put("/campaigns/{campaign_id}", response_model=MarketingCampaignResponse)
def update_campaign(
    campaign_id: int,
    body: MarketingCampaignUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketing.edit")),
):
    company = _get_company(db)
    campaign = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id, MarketingCampaign.company_id == company.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status == "active":
        raise HTTPException(status_code=400, detail="Pause the campaign before editing")
    for field in ("name", "description", "campaign_type", "audience_type", "audience_filter_json"):
        val = getattr(body, field)
        if val is not None:
            setattr(campaign, field, val)
    if body.steps_json is not None:
        campaign.steps_json = [s.model_dump() for s in body.steps_json]
    db.commit()
    db.commit()
    return _campaign_response(campaign)


@router.get("/campaigns/{campaign_id}/enrollments", response_model=list[MarketingEnrollmentItem])
def list_enrollments(
    campaign_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketing.view")),
):
    company = _get_company(db)
    rows = (
        db.query(MarketingEnrollment)
        .options(joinedload(MarketingEnrollment.lead), joinedload(MarketingEnrollment.contact))
        .filter(MarketingEnrollment.company_id == company.id, MarketingEnrollment.campaign_id == campaign_id)
        .order_by(MarketingEnrollment.enrolled_at.desc())
        .limit(100)
        .all()
    )
    return [
        MarketingEnrollmentItem(
            id=e.id,
            lead_id=e.lead_id,
            contact_id=e.contact_id,
            lead_name=e.lead.name if e.lead else None,
            contact_name=e.contact.name if e.contact else None,
            status=e.status,
            current_step=int(e.current_step or 0),
            next_send_at=e.next_send_at,
            enrolled_at=e.enrolled_at,
        )
        for e in rows
    ]


@router.post("/campaigns/{campaign_id}/activate", response_model=MarketingCampaignResponse)
def activate_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("marketing.activate")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    campaign = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id, MarketingCampaign.company_id == company.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.steps_json:
        raise HTTPException(status_code=400, detail="Add at least one step before activating")
    campaign.status = "active"
    campaign.activated_at = _utcnow()
    enroll_audience(db, campaign)
    db.commit()
    db.commit()
    return _campaign_response(campaign)


@router.post("/campaigns/{campaign_id}/pause", response_model=MarketingCampaignResponse)
def pause_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketing.activate")),
):
    company = _get_company(db)
    campaign = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id, MarketingCampaign.company_id == company.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "paused"
    db.commit()
    return _campaign_response(campaign)


@router.post("/process-due")
def process_due(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketing.run")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    count = process_due_enrollments(db, company.id, settings.default_owner_role)
    db.commit()
    return {"processed": count}


@router.get("/campaigns/{campaign_id}/send-logs", response_model=list[MarketingSendLogItem])
def campaign_send_logs(
    campaign_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketing.view")),
):
    company = _get_company(db)
    logs = (
        db.query(MarketingSendLog)
        .join(MarketingEnrollment)
        .filter(MarketingEnrollment.company_id == company.id, MarketingEnrollment.campaign_id == campaign_id)
        .order_by(MarketingSendLog.sent_at.desc())
        .limit(50)
        .all()
    )
    return [
        MarketingSendLogItem(
            id=log.id,
            step_index=log.step_index,
            channel=log.channel,
            status=log.status,
            subject=log.subject,
            body_preview=log.body_preview,
            sent_at=log.sent_at,
        )
        for log in logs
    ]
