"""Workflow Builder API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import Company, User, Workflow, WorkflowRun, WorkflowSettings
from services.workflow_engine import (
    generate_workflow_code,
    process_event,
    valid_module,
    valid_trigger,
)
from workflow_config import (
    ACTION_CATALOG,
    CONDITION_FIELDS,
    DEFAULT_MAX_ACTIVE,
    DEFAULT_RATE_LIMIT_PER_HOUR,
    DEFAULT_RUN_AS_ROLE,
    WORKFLOW_TEMPLATES,
    TRIGGER_CATALOG,
)
from workflow_schemas import (
    CatalogItem,
    WorkflowCreateRequest,
    WorkflowDashboardResponse,
    WorkflowListItem,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowRunListItem,
    WorkflowRunListResponse,
    WorkflowRunResponse,
    WorkflowSettingsResponse,
    WorkflowSettingsUpdateRequest,
    WorkflowTemplateResponse,
    WorkflowTestRequest,
    WorkflowUpdateRequest,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)




def _get_settings(db: Session, company: Company) -> WorkflowSettings:
    settings = db.query(WorkflowSettings).filter(WorkflowSettings.company_id == company.id).first()
    if not settings:
        settings = WorkflowSettings(
            company_id=company.id,
            is_enabled=True,
            max_active_workflows=DEFAULT_MAX_ACTIVE,
            default_run_as_role=DEFAULT_RUN_AS_ROLE,
            rate_limit_per_hour=DEFAULT_RATE_LIMIT_PER_HOUR,
        )
        db.add(settings)
        db.flush()
    return settings


def _require_enabled(settings: WorkflowSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="Workflow Builder module is not enabled")


def _settings_response(settings: WorkflowSettings) -> WorkflowSettingsResponse:
    return WorkflowSettingsResponse(
        is_enabled=settings.is_enabled,
        max_active_workflows=int(settings.max_active_workflows or DEFAULT_MAX_ACTIVE),
        default_run_as_role=settings.default_run_as_role or DEFAULT_RUN_AS_ROLE,
        rate_limit_per_hour=int(settings.rate_limit_per_hour or DEFAULT_RATE_LIMIT_PER_HOUR),
        notify_on_failure=bool(settings.notify_on_failure),
    )


def _workflow_response(wf: Workflow) -> WorkflowResponse:
    return WorkflowResponse(
        id=wf.id,
        workflow_code=wf.workflow_code,
        name=wf.name,
        description=wf.description,
        module=wf.module,
        trigger_type=wf.trigger_type,
        trigger_config_json=wf.trigger_config_json or {},
        conditions_json=wf.conditions_json or [],
        actions_json=wf.actions_json or [],
        priority=int(wf.priority or 100),
        stop_on_match=bool(wf.stop_on_match),
        is_active=bool(wf.is_active),
        run_count=int(wf.run_count or 0),
        last_run_at=wf.last_run_at,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


def _workflow_list_item(wf: Workflow) -> WorkflowListItem:
    return WorkflowListItem(
        id=wf.id,
        workflow_code=wf.workflow_code,
        name=wf.name,
        module=wf.module,
        trigger_type=wf.trigger_type,
        is_active=bool(wf.is_active),
        priority=int(wf.priority or 100),
        run_count=int(wf.run_count or 0),
        last_run_at=wf.last_run_at,
        created_at=wf.created_at,
    )


def _run_list_item(run: WorkflowRun, workflow_name: str | None = None) -> WorkflowRunListItem:
    return WorkflowRunListItem(
        id=run.id,
        run_number=run.run_number,
        workflow_id=run.workflow_id,
        workflow_name=workflow_name,
        trigger_type=run.trigger_type,
        record_type=run.record_type,
        record_id=run.record_id,
        status=run.status,
        is_dry_run=bool(run.is_dry_run),
        triggered_at=run.triggered_at,
        completed_at=run.completed_at,
    )


def _validate_workflow_payload(
    module: str,
    trigger_type: str,
    actions_json: list,
    *,
    for_activate: bool = False,
) -> None:
    if not valid_module(module):
        raise HTTPException(status_code=400, detail="Invalid module")
    if not valid_trigger(trigger_type):
        raise HTTPException(status_code=400, detail="Invalid trigger type")
    if for_activate and not actions_json:
        raise HTTPException(status_code=400, detail="At least one action is required to activate")


def _load_workflow(db: Session, company_id: int, workflow_id: int) -> Workflow:
    wf = db.query(Workflow).filter(Workflow.id == workflow_id, Workflow.company_id == company_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.get("/settings", response_model=WorkflowSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.manage_settings")),
):
    return _settings_response(_get_settings(db, get_current_company(db, user)))


@router.put("/settings", response_model=WorkflowSettingsResponse)
def update_settings(
    payload: WorkflowSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.manage_settings")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    log_activity(
        db,
        "workflow_settings_updated",
        user_id=user.id,
        details=f"company_id={company.id}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(settings)
    return _settings_response(settings)


@router.get("/dashboard", response_model=WorkflowDashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.view")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    today = _utcnow().date()
    active_count = (
        db.query(Workflow)
        .filter(Workflow.company_id == company.id, Workflow.is_active.is_(True))
        .count()
    )
    runs_today = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.company_id == company.id,
            WorkflowRun.is_dry_run.is_(False),
            func.date(WorkflowRun.triggered_at) == today,
        )
        .count()
    )
    failures_today = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.company_id == company.id,
            WorkflowRun.is_dry_run.is_(False),
            WorkflowRun.status.in_(("failed", "partial")),
            func.date(WorkflowRun.triggered_at) == today,
        )
        .count()
    )
    recent = (
        db.query(WorkflowRun, Workflow.name)
        .join(Workflow, Workflow.id == WorkflowRun.workflow_id)
        .filter(WorkflowRun.company_id == company.id)
        .order_by(WorkflowRun.triggered_at.desc())
        .limit(10)
        .all()
    )
    return WorkflowDashboardResponse(
        is_enabled=bool(settings.is_enabled),
        active_count=active_count,
        runs_today=runs_today,
        failures_today=failures_today,
        recent_runs=[_run_list_item(r, name) for r, name in recent],
    )


@router.get("/triggers", response_model=list[CatalogItem])
def list_triggers(_: User = Depends(require_permission("workflows.view"))):
    return [
        CatalogItem(
            key=t["key"],
            label=t["label"],
            module=t["module"],
            record_type=t.get("record_type"),
            config_fields=t.get("config_fields"),
        )
        for t in TRIGGER_CATALOG
    ]


@router.get("/actions", response_model=list[CatalogItem])
def list_actions(_: User = Depends(require_permission("workflows.view"))):
    return [CatalogItem(key=a["key"], label=a["label"], fields=a.get("fields")) for a in ACTION_CATALOG]


@router.get("/condition-fields")
def condition_fields(
    record_type: str = Query(...),
    _: User = Depends(require_permission("workflows.view")),
):
    return CONDITION_FIELDS.get(record_type, [])


@router.get("/templates", response_model=list[WorkflowTemplateResponse])
def list_templates(_: User = Depends(require_permission("workflows.view"))):
    return [WorkflowTemplateResponse(**t) for t in WORKFLOW_TEMPLATES]


@router.post("/templates/{template_key}", response_model=WorkflowResponse)
def duplicate_template(
    template_key: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.create")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    tpl = next((t for t in WORKFLOW_TEMPLATES if t["key"] == template_key), None)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    wf = Workflow(
        company_id=company.id,
        workflow_code=generate_workflow_code(db, company.id),
        name=tpl["name"],
        description=tpl.get("description"),
        module=tpl["module"],
        trigger_type=tpl["trigger_type"],
        trigger_config_json=tpl.get("trigger_config_json", {}),
        conditions_json=tpl.get("conditions_json", []),
        actions_json=tpl.get("actions_json", []),
        priority=int(tpl.get("priority", 100)),
        stop_on_match=bool(tpl.get("stop_on_match", False)),
        is_active=False,
        created_by_id=user.id,
    )
    db.add(wf)
    log_activity(
        db,
        "workflow_created",
        user_id=user.id,
        details=f"From template {template_key}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(wf)
    return _workflow_response(wf)


@router.get("", response_model=WorkflowListResponse)
def list_workflows(
    module: str | None = None,
    is_active: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.view")),
):
    company = get_current_company(db, user)
    q = db.query(Workflow).filter(Workflow.company_id == company.id)
    if module:
        q = q.filter(Workflow.module == module)
    if is_active is not None:
        q = q.filter(Workflow.is_active.is_(is_active))
    total = q.count()
    items = q.order_by(Workflow.priority.asc(), Workflow.created_at.desc()).offset(skip).limit(limit).all()
    return WorkflowListResponse(items=[_workflow_list_item(w) for w in items], total=total)


@router.post("", response_model=WorkflowResponse)
def create_workflow(
    payload: WorkflowCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.create")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    _validate_workflow_payload(payload.module, payload.trigger_type, payload.actions_json)
    wf = Workflow(
        company_id=company.id,
        workflow_code=generate_workflow_code(db, company.id),
        name=payload.name,
        description=payload.description,
        module=payload.module,
        trigger_type=payload.trigger_type,
        trigger_config_json=payload.trigger_config_json,
        conditions_json=payload.conditions_json,
        actions_json=payload.actions_json,
        priority=payload.priority,
        stop_on_match=payload.stop_on_match,
        is_active=False,
        created_by_id=user.id,
    )
    db.add(wf)
    log_activity(
        db,
        "workflow_created",
        user_id=user.id,
        details=wf.name,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(wf)
    return _workflow_response(wf)


@router.get("/runs", response_model=WorkflowRunListResponse)
def list_runs(
    workflow_id: int | None = None,
    status: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.view")),
):
    company = get_current_company(db, user)
    q = (
        db.query(WorkflowRun, Workflow.name)
        .join(Workflow, Workflow.id == WorkflowRun.workflow_id)
        .filter(WorkflowRun.company_id == company.id)
    )
    if workflow_id:
        q = q.filter(WorkflowRun.workflow_id == workflow_id)
    if status:
        q = q.filter(WorkflowRun.status == status)
    total = q.count()
    rows = q.order_by(WorkflowRun.triggered_at.desc()).offset(skip).limit(limit).all()
    return WorkflowRunListResponse(
        items=[_run_list_item(r, name) for r, name in rows],
        total=total,
    )


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.view")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    row = (
        db.query(WorkflowRun, Workflow.name)
        .join(Workflow, Workflow.id == WorkflowRun.workflow_id)
        .filter(WorkflowRun.id == run_id, WorkflowRun.company_id == company.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    run, name = row
    return WorkflowRunResponse(
        id=run.id,
        run_number=run.run_number,
        workflow_id=run.workflow_id,
        workflow_name=name,
        trigger_type=run.trigger_type,
        record_type=run.record_type,
        record_id=run.record_id,
        status=run.status,
        conditions_result_json=run.conditions_result_json or [],
        actions_result_json=run.actions_result_json or [],
        error_message=run.error_message,
        is_dry_run=bool(run.is_dry_run),
        triggered_at=run.triggered_at,
        completed_at=run.completed_at,
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.view")),
):
    company = get_current_company(db, user)
    return _workflow_response(_load_workflow(db, company.id, workflow_id))


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: int,
    payload: WorkflowUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.edit")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    wf = _load_workflow(db, company.id, workflow_id)
    if wf.is_active:
        raise HTTPException(status_code=400, detail="Deactivate workflow before editing")
    data = payload.model_dump(exclude_unset=True)
    if "module" in data or "trigger_type" in data or "actions_json" in data:
        _validate_workflow_payload(
            data.get("module", wf.module),
            data.get("trigger_type", wf.trigger_type),
            data.get("actions_json", wf.actions_json or []),
        )
    for key, value in data.items():
        setattr(wf, key, value)
    wf.updated_by_id = user.id
    log_activity(
        db,
        "workflow_updated",
        user_id=user.id,
        details=wf.workflow_code,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(wf)
    return _workflow_response(wf)


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.delete")),
):
    company = get_current_company(db, user)
    wf = _load_workflow(db, company.id, workflow_id)
    if wf.is_active:
        raise HTTPException(status_code=400, detail="Deactivate workflow before deleting")
    code = wf.workflow_code
    db.delete(wf)
    log_activity(
        db,
        "workflow_deleted",
        user_id=user.id,
        details=code,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"ok": True}


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse)
def duplicate_workflow(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.create")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    src = _load_workflow(db, company.id, workflow_id)
    wf = Workflow(
        company_id=company.id,
        workflow_code=generate_workflow_code(db, company.id),
        name=f"{src.name} (copy)",
        description=src.description,
        module=src.module,
        trigger_type=src.trigger_type,
        trigger_config_json=src.trigger_config_json or {},
        conditions_json=src.conditions_json or [],
        actions_json=src.actions_json or [],
        priority=int(src.priority or 100),
        stop_on_match=bool(src.stop_on_match),
        is_active=False,
        created_by_id=user.id,
    )
    db.add(wf)
    log_activity(
        db,
        "workflow_duplicated",
        user_id=user.id,
        details=f"{src.workflow_code} -> {wf.workflow_code}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(wf)
    return _workflow_response(wf)


@router.post("/{workflow_id}/activate", response_model=WorkflowResponse)
def activate_workflow(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.activate")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    wf = _load_workflow(db, company.id, workflow_id)
    _validate_workflow_payload(wf.module, wf.trigger_type, wf.actions_json or [], for_activate=True)
    active_count = (
        db.query(Workflow)
        .filter(Workflow.company_id == company.id, Workflow.is_active.is_(True), Workflow.id != wf.id)
        .count()
    )
    if active_count >= int(settings.max_active_workflows or DEFAULT_MAX_ACTIVE):
        raise HTTPException(status_code=400, detail="Maximum active workflows reached")
    wf.is_active = True
    wf.updated_by_id = user.id
    log_activity(
        db,
        "workflow_activated",
        user_id=user.id,
        details=wf.workflow_code,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(wf)
    return _workflow_response(wf)


@router.post("/{workflow_id}/deactivate", response_model=WorkflowResponse)
def deactivate_workflow(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.activate")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    wf = _load_workflow(db, company.id, workflow_id)
    wf.is_active = False
    wf.updated_by_id = user.id
    log_activity(
        db,
        "workflow_deactivated",
        user_id=user.id,
        details=wf.workflow_code,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(wf)
    return _workflow_response(wf)


@router.post("/{workflow_id}/test", response_model=WorkflowRunResponse)
def test_workflow(
    workflow_id: int,
    payload: WorkflowTestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("workflows.test")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    wf = _load_workflow(db, company.id, workflow_id)
    runs = process_event(
        db,
        company_id=company.id,
        settings=settings,
        trigger_type=wf.trigger_type,
        record_type=payload.record_type,
        record_id=payload.record_id,
        payload={},
        actor_id=user.id,
        dry_run=True,
        workflow_id=wf.id,
    )
    if not runs:
        raise HTTPException(status_code=400, detail="Dry-run produced no result")
    db.commit()
    run = runs[0]
    return WorkflowRunResponse(
        id=run.id,
        run_number=run.run_number,
        workflow_id=run.workflow_id,
        workflow_name=wf.name,
        trigger_type=run.trigger_type,
        record_type=run.record_type,
        record_id=run.record_id,
        status=run.status,
        conditions_result_json=run.conditions_result_json or [],
        actions_result_json=run.actions_result_json or [],
        error_message=run.error_message,
        is_dry_run=True,
        triggered_at=run.triggered_at,
        completed_at=run.completed_at,
    )
