"""AI Reports API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from ai_reports_config import DEFAULT_DOMAINS, DEFAULT_GENERATION_MODE, DEFAULT_NOTIFY_ROLES, DEFAULT_PERIOD, DEFAULT_RUN_PREFIX
from ai_reports_schemas import (
    AiReportSettingsResponse,
    AiReportSettingsUpdateRequest,
    AiReportsDashboardResponse,
    GenerateInsightRequest,
    InsightBullet,
    InsightRunListItem,
    InsightRunListResponse,
    InsightRunResponse,
    InsightSectionResponse,
    PermittedDomainsResponse,
    WatchItem,
)
from auth_utils import get_client_ip, get_db, require_permission
from models import AiInsightRun, AiInsightSection, AiReportSettings, Company, User
from services.ai_insight_service import (
    aggregate_watch_from_run,
    generate_run_number,
    permitted_domains,
    resolve_period,
    run_insight_generation,
)

router = APIRouter(prefix="/ai-reports", tags=["ai-reports"])


def _get_company(db: Session) -> Company:
    company = db.query(Company).first()
    if not company:
        raise HTTPException(status_code=400, detail="Company must be configured")
    return company


def _get_settings(db: Session, company: Company) -> AiReportSettings:
    settings = db.query(AiReportSettings).filter(AiReportSettings.company_id == company.id).first()
    if settings:
        return settings
    settings = AiReportSettings(
        company_id=company.id,
        is_enabled=True,
        default_period=DEFAULT_PERIOD,
        default_domains_json=DEFAULT_DOMAINS,
        notify_roles_json=DEFAULT_NOTIFY_ROLES,
        generation_mode=DEFAULT_GENERATION_MODE,
    )
    db.add(settings)
    db.flush()
    return settings


def _require_enabled(settings: AiReportSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="AI Reports module is not enabled")


def _settings_response(settings: AiReportSettings) -> AiReportSettingsResponse:
    return AiReportSettingsResponse(
        is_enabled=settings.is_enabled,
        default_period=settings.default_period or DEFAULT_PERIOD,
        default_domains_json=settings.default_domains_json or DEFAULT_DOMAINS,
        include_executive_brief=bool(settings.include_executive_brief),
        anomaly_thresholds_json=settings.anomaly_thresholds_json or {},
        notify_roles_json=settings.notify_roles_json or [],
        generation_mode=settings.generation_mode or DEFAULT_GENERATION_MODE,
    )


def _run_list_item(run: AiInsightRun) -> InsightRunListItem:
    return InsightRunListItem(
        id=run.id,
        run_number=run.run_number,
        period_start=run.period_start,
        period_end=run.period_end,
        domains_json=run.domains_json or [],
        status=run.status,
        executive_headline=run.executive_headline,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def _section_response(section: AiInsightSection) -> InsightSectionResponse:
    bullets = [InsightBullet(**b) for b in (section.bullets_json or [])]
    watch = [WatchItem(**w) for w in (section.watch_items_json or [])]
    return InsightSectionResponse(
        id=section.id,
        domain=section.domain,
        headline=section.headline,
        narrative=section.narrative,
        bullets=bullets,
        watch_items=watch,
        metrics_json=section.metrics_json or {},
        sort_order=int(section.sort_order or 0),
    )


def _load_run(db: Session, company_id: int, run_id: int) -> AiInsightRun:
    run = (
        db.query(AiInsightRun)
        .options(joinedload(AiInsightRun.sections))
        .filter(AiInsightRun.id == run_id, AiInsightRun.company_id == company_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Insight run not found")
    return run


def _run_response(run: AiInsightRun) -> InsightRunResponse:
    sections = sorted(run.sections or [], key=lambda s: s.sort_order)
    watch = aggregate_watch_from_run(run)
    return InsightRunResponse(
        id=run.id,
        run_number=run.run_number,
        period_start=run.period_start,
        period_end=run.period_end,
        domains_json=run.domains_json or [],
        status=run.status,
        executive_headline=run.executive_headline,
        executive_summary=run.executive_summary,
        error_message=run.error_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
        sections=[_section_response(s) for s in sections],
        watch_items=[WatchItem(**w) for w in watch],
    )


@router.get("/settings", response_model=AiReportSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("ai_reports.view")),
):
    company = _get_company(db)
    return _settings_response(_get_settings(db, company))


@router.put("/settings", response_model=AiReportSettingsResponse)
def update_settings(
    payload: AiReportSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ai_reports.manage_settings")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    log_activity(
        db,
        "ai_reports_settings_updated",
        user_id=user.id,
        details={"company_id": company.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(settings)
    return _settings_response(settings)


@router.get("/domains", response_model=PermittedDomainsResponse)
def get_domains(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ai_reports.view")),
):
    return PermittedDomainsResponse(domains=permitted_domains(db, user))


@router.get("/dashboard", response_model=AiReportsDashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ai_reports.view")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))

    runs = (
        db.query(AiInsightRun)
        .options(joinedload(AiInsightRun.sections))
        .filter(AiInsightRun.company_id == company.id)
        .order_by(AiInsightRun.created_at.desc())
        .limit(20)
        .all()
    )
    latest = next((r for r in runs if r.status == "completed"), None)
    watch: list[WatchItem] = []
    if latest:
        watch = [WatchItem(**w) for w in aggregate_watch_from_run(latest)]

    return AiReportsDashboardResponse(
        latest_run=_run_list_item(latest) if latest else None,
        recent_runs=[_run_list_item(r) for r in runs],
        watch_items=watch,
    )


@router.get("/runs", response_model=InsightRunListResponse)
def list_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("ai_reports.view")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))
    q = db.query(AiInsightRun).filter(AiInsightRun.company_id == company.id)
    total = q.count()
    runs = q.order_by(AiInsightRun.created_at.desc()).offset(skip).limit(limit).all()
    return InsightRunListResponse(items=[_run_list_item(r) for r in runs], total=total)


@router.get("/runs/{run_id}", response_model=InsightRunResponse)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("ai_reports.view")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))
    return _run_response(_load_run(db, company.id, run_id))


@router.post("/generate", response_model=InsightRunResponse)
def generate_insight(
    payload: GenerateInsightRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ai_reports.generate")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    period_start, period_end = resolve_period(payload.period, payload.period_start, payload.period_end)
    if period_end < period_start:
        raise HTTPException(status_code=400, detail="period_end must be >= period_start")
    if (period_end - period_start).days > 366:
        raise HTTPException(status_code=400, detail="Period range cannot exceed 366 days")

    domains = payload.domains or settings.default_domains_json or DEFAULT_DOMAINS
    allowed = permitted_domains(db, user)
    domains = [d for d in domains if d in allowed]
    if not domains:
        raise HTTPException(status_code=400, detail="No permitted domains selected")

    run = AiInsightRun(
        company_id=company.id,
        run_number=generate_run_number(db, company.id, DEFAULT_RUN_PREFIX),
        period_start=period_start,
        period_end=period_end,
        domains_json=domains,
        status="pending",
        generated_by_id=user.id,
    )
    db.add(run)
    db.flush()

    run_insight_generation(
        db,
        company,
        user,
        settings,
        run,
        domains,
        payload.include_executive_brief,
    )
    log_activity(
        db,
        "ai_insight_generated",
        user_id=user.id,
        details={"run_id": run.id, "run_number": run.run_number, "period": f"{period_start}/{period_end}"},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _run_response(_load_run(db, company.id, run.id))
