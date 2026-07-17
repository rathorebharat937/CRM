"""Quality Control API."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import (
    Company,
    CorrectiveAction,
    InspectionPoint,
    Product,
    PurchaseOrder,
    QualityAlert,
    QualityChecklistTemplate,
    QualityInspection,
    QualitySettings,
    User,
    WorkOrder,
)
from quality_config import CAPA_ACTION_TYPES, CAPA_STATUSES, INSPECTION_STATUSES, TEMPLATE_STATUSES
from quality_schemas import (
    AlertListItem,
    AlertListResponse,
    CapaCreateRequest,
    CapaListItem,
    CapaListResponse,
    CapaResponse,
    CapaUpdateRequest,
    InspectionCreateRequest,
    InspectionListItem,
    InspectionListResponse,
    InspectionPointResponse,
    InspectionPointUpdateRequest,
    InspectionResponse,
    InspectionSubmitRequest,
    InspectionWaiveRequest,
    QualityDashboardResponse,
    QualitySettingsResponse,
    QualitySettingsUpdateRequest,
    TemplateCreateRequest,
    TemplateListItem,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdateRequest,
)
from services.quality_service import (
    create_inspection,
    generate_capa_number,
    get_quality_settings,
    seed_inspection_points,
    submit_inspection,
    sync_overdue_capa_alerts,
    sync_overdue_inspection_alerts,
    waive_inspection,
)

router = APIRouter(prefix="/quality", tags=["quality"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)




def _require_enabled(settings: QualitySettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="Quality Control is not enabled")


def _settings_response(settings: QualitySettings) -> QualitySettingsResponse:
    return QualitySettingsResponse(
        is_enabled=settings.is_enabled,
        inspection_number_prefix=settings.inspection_number_prefix,
        capa_number_prefix=settings.capa_number_prefix,
        default_incoming_required=settings.default_incoming_required,
        block_on_fail_default=settings.block_on_fail_default,
        alert_repeat_fail_threshold=int(settings.alert_repeat_fail_threshold or 3),
        alert_overdue_hours=int(settings.alert_overdue_hours or 24),
        notify_roles_json=settings.notify_roles_json or [],
    )


def _reference_label(db: Session, insp: QualityInspection) -> str | None:
    if insp.reference_type == "work_order" and insp.reference_id:
        wo = db.query(WorkOrder).filter(WorkOrder.id == insp.reference_id).first()
        return wo.work_order_number if wo else f"WO #{insp.reference_id}"
    if insp.reference_type == "purchase_order" and insp.reference_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == insp.reference_id).first()
        return po.po_number if po else f"PO #{insp.reference_id}"
    return None


def _inspection_list_item(db: Session, insp: QualityInspection) -> InspectionListItem:
    point = insp.inspection_point
    product = insp.product
    if not product and insp.work_order and insp.work_order.product:
        product = insp.work_order.product
    return InspectionListItem(
        id=insp.id,
        inspection_number=insp.inspection_number,
        inspection_point_code=point.code if point else None,
        inspection_point_name=point.name if point else None,
        product_id=insp.product_id,
        product_name=product.name if product else None,
        reference_type=insp.reference_type,
        reference_label=_reference_label(db, insp),
        status=insp.status,
        inspected_at=insp.inspected_at,
        inspected_by_name=insp.inspected_by.name if insp.inspected_by else None,
        created_at=insp.created_at,
    )


def _inspection_response(db: Session, insp: QualityInspection) -> InspectionResponse:
    point = insp.inspection_point
    product = insp.product
    if not product and insp.work_order and insp.work_order.product:
        product = insp.work_order.product
    return InspectionResponse(
        id=insp.id,
        inspection_number=insp.inspection_number,
        inspection_point_id=insp.inspection_point_id,
        inspection_point_code=point.code if point else None,
        inspection_point_name=point.name if point else None,
        template_id=insp.template_id,
        status=insp.status,
        checklist_json=insp.checklist_json or [],
        overall_notes=insp.notes,
        reference_type=insp.reference_type,
        reference_id=insp.reference_id,
        reference_label=_reference_label(db, insp),
        product_id=insp.product_id,
        product_name=product.name if product else None,
        work_order_id=insp.work_order_id,
        inspected_by_id=insp.inspected_by_id,
        inspected_by_name=insp.inspected_by.name if insp.inspected_by else None,
        inspected_at=insp.inspected_at,
        waived_by_id=insp.waived_by_id,
        waived_by_name=insp.waived_by.name if insp.waived_by else None,
        waiver_reason=insp.waiver_reason,
        created_at=insp.created_at,
    )


def _get_inspection(db: Session, company_id: int, inspection_id: int) -> QualityInspection:
    insp = (
        db.query(QualityInspection)
        .options(
            joinedload(QualityInspection.inspection_point),
            joinedload(QualityInspection.product),
            joinedload(QualityInspection.inspected_by),
            joinedload(QualityInspection.waived_by),
            joinedload(QualityInspection.work_order).joinedload(WorkOrder.product),
        )
        .filter(QualityInspection.company_id == company_id, QualityInspection.id == inspection_id)
        .first()
    )
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return insp


@router.get("/dashboard", response_model=QualityDashboardResponse)
def quality_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.view")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    sync_overdue_inspection_alerts(db, company)
    sync_overdue_capa_alerts(db, company)
    db.commit()

    since_7d = _utcnow() - timedelta(days=7)
    since_30d = _utcnow() - timedelta(days=30)
    pending = (
        db.query(func.count(QualityInspection.id))
        .filter(QualityInspection.company_id == company.id, QualityInspection.status == "pending")
        .scalar()
    )
    failed_7d = (
        db.query(func.count(QualityInspection.id))
        .filter(
            QualityInspection.company_id == company.id,
            QualityInspection.status == "failed",
            QualityInspection.inspected_at >= since_7d,
        )
        .scalar()
    )
    total_30d = (
        db.query(func.count(QualityInspection.id))
        .filter(
            QualityInspection.company_id == company.id,
            QualityInspection.status.in_(["passed", "failed", "waived"]),
            QualityInspection.inspected_at >= since_30d,
        )
        .scalar()
    )
    passed_30d = (
        db.query(func.count(QualityInspection.id))
        .filter(
            QualityInspection.company_id == company.id,
            QualityInspection.status.in_(["passed", "waived"]),
            QualityInspection.inspected_at >= since_30d,
        )
        .scalar()
    )
    pass_rate = round((_float(passed_30d) / _float(total_30d)) * 100, 1) if total_30d else 100.0
    open_alerts = (
        db.query(func.count(QualityAlert.id))
        .filter(QualityAlert.company_id == company.id, QualityAlert.status == "open")
        .scalar()
    )
    open_capas = (
        db.query(func.count(CorrectiveAction.id))
        .filter(CorrectiveAction.company_id == company.id, CorrectiveAction.status.in_(["open", "in_progress", "verified"]))
        .scalar()
    )
    today = _utcnow().date()
    overdue_capas = (
        db.query(func.count(CorrectiveAction.id))
        .filter(
            CorrectiveAction.company_id == company.id,
            CorrectiveAction.status.in_(["open", "in_progress"]),
            CorrectiveAction.due_date.isnot(None),
            CorrectiveAction.due_date < today,
        )
        .scalar()
    )

    pending_q = (
        db.query(QualityInspection)
        .options(
            joinedload(QualityInspection.inspection_point),
            joinedload(QualityInspection.product),
            joinedload(QualityInspection.inspected_by),
            joinedload(QualityInspection.work_order).joinedload(WorkOrder.product),
        )
        .filter(QualityInspection.company_id == company.id, QualityInspection.status == "pending")
        .order_by(QualityInspection.id.desc())
        .limit(10)
        .all()
    )
    failures = (
        db.query(QualityInspection)
        .options(
            joinedload(QualityInspection.inspection_point),
            joinedload(QualityInspection.product),
            joinedload(QualityInspection.inspected_by),
            joinedload(QualityInspection.work_order).joinedload(WorkOrder.product),
        )
        .filter(QualityInspection.company_id == company.id, QualityInspection.status == "failed")
        .order_by(QualityInspection.inspected_at.desc())
        .limit(5)
        .all()
    )
    alerts_db = (
        db.query(QualityAlert)
        .options(joinedload(QualityAlert.product))
        .filter(QualityAlert.company_id == company.id, QualityAlert.status == "open")
        .order_by(QualityAlert.id.desc())
        .limit(10)
        .all()
    )
    capas_db = (
        db.query(CorrectiveAction)
        .options(
            joinedload(CorrectiveAction.inspection),
            joinedload(CorrectiveAction.assigned_to),
        )
        .filter(CorrectiveAction.company_id == company.id, CorrectiveAction.status.in_(["open", "in_progress", "verified"]))
        .order_by(CorrectiveAction.id.desc())
        .limit(10)
        .all()
    )

    return QualityDashboardResponse(
        pending_inspections=int(pending or 0),
        failed_inspections_7d=int(failed_7d or 0),
        pass_rate_30d=pass_rate,
        open_alerts=int(open_alerts or 0),
        open_capas=int(open_capas or 0),
        overdue_capas=int(overdue_capas or 0),
        pending_queue=[_inspection_list_item(db, i) for i in pending_q],
        recent_failures=[_inspection_list_item(db, i) for i in failures],
        open_alerts_list=[
            AlertListItem(
                id=a.id,
                alert_type=a.alert_type,
                severity=a.severity,
                title=a.title,
                message=a.message,
                status=a.status,
                inspection_id=a.inspection_id,
                capa_id=a.capa_id,
                product_name=a.product.name if a.product else None,
                created_at=a.created_at,
            )
            for a in alerts_db
        ],
        open_capas_list=[_capa_list_item(c) for c in capas_db],
    )


def _capa_list_item(capa: CorrectiveAction) -> CapaListItem:
    insp = capa.inspection
    product_name = None
    if insp and insp.product:
        product_name = insp.product.name
    today = _utcnow().date()
    return CapaListItem(
        id=capa.id,
        capa_number=capa.capa_number,
        title=capa.title,
        status=capa.status,
        action_type=capa.action_type,
        inspection_number=insp.inspection_number if insp else None,
        product_name=product_name,
        assigned_to_name=capa.assigned_to.name if capa.assigned_to else None,
        due_date=capa.due_date,
        is_overdue=bool(capa.due_date and capa.due_date < today and capa.status not in ("closed",)),
    )


def _capa_response(capa: CorrectiveAction) -> CapaResponse:
    insp = capa.inspection
    return CapaResponse(
        id=capa.id,
        capa_number=capa.capa_number,
        inspection_id=capa.inspection_id,
        inspection_number=insp.inspection_number if insp else None,
        title=capa.title,
        description=capa.description,
        action_type=capa.action_type,
        status=capa.status,
        assigned_to_id=capa.assigned_to_id,
        assigned_to_name=capa.assigned_to.name if capa.assigned_to else None,
        due_date=capa.due_date,
        root_cause=capa.root_cause,
        corrective_steps=capa.corrective_steps or "",
        verification_notes=capa.verification_notes,
        closed_by_name=capa.closed_by.name if capa.closed_by else None,
        closed_at=capa.closed_at,
        created_at=capa.created_at,
    )


@router.get("/settings", response_model=QualitySettingsResponse)
def get_settings(db: Session = Depends(get_db), user: User = Depends(require_permission("quality.view"))):
    return _settings_response(get_quality_settings(db, get_current_company(db, user)))


@router.put("/settings", response_model=QualitySettingsResponse)
def update_settings(
    body: QualitySettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.manage_settings")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    if settings.is_enabled:
        seed_inspection_points(db, company.id)
    db.commit()
    db.refresh(settings)
    log_activity(db, "quality_settings_updated", user_id=user.id, details={"is_enabled": settings.is_enabled}, ip_address=get_client_ip(request))
    return _settings_response(settings)


@router.get("/inspection-points", response_model=list[InspectionPointResponse])
def list_inspection_points(db: Session = Depends(get_db), user: User = Depends(require_permission("quality.view"))):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    points = (
        db.query(InspectionPoint)
        .filter(InspectionPoint.company_id == company.id)
        .order_by(InspectionPoint.sort_order, InspectionPoint.id)
        .all()
    )
    return [
        InspectionPointResponse(
            id=p.id,
            code=p.code,
            name=p.name,
            point_type=p.point_type,
            trigger=p.trigger,
            is_active=p.is_active,
            block_on_fail=p.block_on_fail,
            default_template_id=p.default_template_id,
            sort_order=p.sort_order,
        )
        for p in points
    ]


@router.put("/inspection-points/{point_id}", response_model=InspectionPointResponse)
def update_inspection_point(
    point_id: int,
    body: InspectionPointUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.manage_templates")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    point = db.query(InspectionPoint).filter(InspectionPoint.company_id == company.id, InspectionPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404, detail="Inspection point not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(point, key, value)
    db.commit()
    db.refresh(point)
    log_activity(db, "inspection_point_updated", user_id=user.id, details={"point_id": point.id}, ip_address=get_client_ip(request))
    return InspectionPointResponse(
        id=point.id,
        code=point.code,
        name=point.name,
        point_type=point.point_type,
        trigger=point.trigger,
        is_active=point.is_active,
        block_on_fail=point.block_on_fail,
        default_template_id=point.default_template_id,
        sort_order=point.sort_order,
    )


@router.get("/templates", response_model=TemplateListResponse)
def list_templates(db: Session = Depends(get_db), user: User = Depends(require_permission("quality.view"))):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    templates = (
        db.query(QualityChecklistTemplate)
        .options(joinedload(QualityChecklistTemplate.product), joinedload(QualityChecklistTemplate.inspection_point))
        .filter(QualityChecklistTemplate.company_id == company.id)
        .order_by(QualityChecklistTemplate.id.desc())
        .all()
    )
    items = [
        TemplateListItem(
            id=t.id,
            name=t.name,
            product_id=t.product_id,
            product_name=t.product.name if t.product else None,
            inspection_point_id=t.inspection_point_id,
            inspection_point_name=t.inspection_point.name if t.inspection_point else None,
            version=t.version,
            status=t.status,
            item_count=len(t.items_json or []),
        )
        for t in templates
    ]
    return TemplateListResponse(items=items, total=len(items))


@router.post("/templates", response_model=TemplateResponse)
def create_template(
    body: TemplateCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.manage_templates")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    if not body.items_json:
        raise HTTPException(status_code=400, detail="Template requires at least one checklist item")
    tmpl = QualityChecklistTemplate(
        company_id=company.id,
        name=body.name,
        product_id=body.product_id,
        inspection_point_id=body.inspection_point_id,
        version=body.version,
        items_json=body.items_json,
        created_by_id=user.id,
    )
    db.add(tmpl)
    db.commit()
    tmpl = (
        db.query(QualityChecklistTemplate)
        .options(joinedload(QualityChecklistTemplate.product), joinedload(QualityChecklistTemplate.inspection_point))
        .filter(QualityChecklistTemplate.id == tmpl.id)
        .first()
    )
    log_activity(db, "quality_template_created", user_id=user.id, details={"template_id": tmpl.id}, ip_address=get_client_ip(request))
    return _template_response(tmpl)


def _template_response(tmpl: QualityChecklistTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=tmpl.id,
        name=tmpl.name,
        product_id=tmpl.product_id,
        product_name=tmpl.product.name if tmpl.product else None,
        inspection_point_id=tmpl.inspection_point_id,
        inspection_point_name=tmpl.inspection_point.name if tmpl.inspection_point else None,
        version=tmpl.version,
        status=tmpl.status,
        items_json=tmpl.items_json or [],
        created_at=tmpl.created_at,
    )


@router.get("/templates/{template_id}", response_model=TemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("quality.view"))):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    tmpl = (
        db.query(QualityChecklistTemplate)
        .options(joinedload(QualityChecklistTemplate.product), joinedload(QualityChecklistTemplate.inspection_point))
        .filter(QualityChecklistTemplate.company_id == company.id, QualityChecklistTemplate.id == template_id)
        .first()
    )
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_response(tmpl)


@router.put("/templates/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    body: TemplateUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.manage_templates")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    tmpl = (
        db.query(QualityChecklistTemplate)
        .options(joinedload(QualityChecklistTemplate.product), joinedload(QualityChecklistTemplate.inspection_point))
        .filter(QualityChecklistTemplate.company_id == company.id, QualityChecklistTemplate.id == template_id)
        .first()
    )
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.status == "archived":
        raise HTTPException(status_code=400, detail="Archived template cannot be edited")
    data = body.model_dump(exclude_unset=True)
    if "items_json" in data and not data["items_json"]:
        raise HTTPException(status_code=400, detail="Template requires at least one checklist item")
    for key, value in data.items():
        setattr(tmpl, key, value)
    db.commit()
    db.refresh(tmpl)
    log_activity(db, "quality_template_updated", user_id=user.id, details={"template_id": tmpl.id}, ip_address=get_client_ip(request))
    return _template_response(tmpl)


@router.post("/templates/{template_id}/activate", response_model=TemplateResponse)
def activate_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.manage_templates")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    tmpl = (
        db.query(QualityChecklistTemplate)
        .options(joinedload(QualityChecklistTemplate.product), joinedload(QualityChecklistTemplate.inspection_point))
        .filter(QualityChecklistTemplate.company_id == company.id, QualityChecklistTemplate.id == template_id)
        .first()
    )
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if not tmpl.items_json:
        raise HTTPException(status_code=400, detail="Template requires checklist items")
    q = db.query(QualityChecklistTemplate).filter(
        QualityChecklistTemplate.company_id == company.id,
        QualityChecklistTemplate.status == "active",
        QualityChecklistTemplate.id != tmpl.id,
    )
    if tmpl.product_id:
        q = q.filter(QualityChecklistTemplate.product_id == tmpl.product_id)
    if tmpl.inspection_point_id:
        q = q.filter(QualityChecklistTemplate.inspection_point_id == tmpl.inspection_point_id)
    q.update({"status": "archived"})
    tmpl.status = "active"
    db.commit()
    db.refresh(tmpl)
    log_activity(db, "quality_template_activated", user_id=user.id, details={"template_id": tmpl.id}, ip_address=get_client_ip(request))
    return _template_response(tmpl)


@router.get("/inspections", response_model=InspectionListResponse)
def list_inspections(
    status: str | None = None,
    point_code: str | None = None,
    product_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.view")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    q = (
        db.query(QualityInspection)
        .options(
            joinedload(QualityInspection.inspection_point),
            joinedload(QualityInspection.product),
            joinedload(QualityInspection.inspected_by),
            joinedload(QualityInspection.work_order).joinedload(WorkOrder.product),
        )
        .filter(QualityInspection.company_id == company.id)
    )
    if status:
        q = q.filter(QualityInspection.status == status)
    if product_id:
        q = q.filter(QualityInspection.product_id == product_id)
    if point_code:
        q = q.join(InspectionPoint).filter(InspectionPoint.code == point_code)
    items = q.order_by(QualityInspection.id.desc()).all()
    return InspectionListResponse(items=[_inspection_list_item(db, i) for i in items], total=len(items))


@router.post("/inspections", response_model=InspectionResponse)
def create_manual_inspection(
    body: InspectionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.inspect")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    point = db.query(InspectionPoint).filter(InspectionPoint.company_id == company.id, InspectionPoint.id == body.inspection_point_id).first()
    if not point:
        raise HTTPException(status_code=404, detail="Inspection point not found")
    work_order_id = body.reference_id if body.reference_type == "work_order" else None
    insp = create_inspection(
        db,
        company,
        inspection_point_id=body.inspection_point_id,
        product_id=body.product_id,
        template_id=body.template_id,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
        work_order_id=work_order_id,
        notes=body.overall_notes,
    )
    db.commit()
    insp = _get_inspection(db, company.id, insp.id)
    log_activity(db, "quality_inspection_created", user_id=user.id, details={"inspection_id": insp.id}, ip_address=get_client_ip(request))
    return _inspection_response(db, insp)


@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
def get_inspection(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("quality.view"))):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    return _inspection_response(db, _get_inspection(db, company.id, inspection_id))


@router.put("/inspections/{inspection_id}/submit", response_model=InspectionResponse)
def submit_inspection_endpoint(
    inspection_id: int,
    body: InspectionSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.inspect")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    insp = _get_inspection(db, company.id, inspection_id)
    try:
        submit_inspection(db, company, insp, user, body.checklist_json, body.overall_notes, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    insp = _get_inspection(db, company.id, inspection_id)
    log_activity(db, "quality_inspection_submitted", user_id=user.id, details={"inspection_id": insp.id, "status": insp.status}, ip_address=get_client_ip(request))
    return _inspection_response(db, insp)


@router.put("/inspections/{inspection_id}/waive", response_model=InspectionResponse)
def waive_inspection_endpoint(
    inspection_id: int,
    body: InspectionWaiveRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.waive")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    if not body.waiver_reason.strip():
        raise HTTPException(status_code=400, detail="Waiver reason is required")
    insp = _get_inspection(db, company.id, inspection_id)
    try:
        waive_inspection(db, company, insp, user, body.waiver_reason.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    insp = _get_inspection(db, company.id, inspection_id)
    log_activity(db, "quality_inspection_waived", user_id=user.id, details={"inspection_id": insp.id}, ip_address=get_client_ip(request))
    return _inspection_response(db, insp)


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    status: str = Query(default="open"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.view")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    q = db.query(QualityAlert).options(joinedload(QualityAlert.product)).filter(QualityAlert.company_id == company.id)
    if status:
        q = q.filter(QualityAlert.status == status)
    alerts = q.order_by(QualityAlert.id.desc()).all()
    return AlertListResponse(
        items=[
            AlertListItem(
                id=a.id,
                alert_type=a.alert_type,
                severity=a.severity,
                title=a.title,
                message=a.message,
                status=a.status,
                inspection_id=a.inspection_id,
                capa_id=a.capa_id,
                product_name=a.product.name if a.product else None,
                created_at=a.created_at,
            )
            for a in alerts
        ],
        total=len(alerts),
    )


@router.put("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.manage_alerts")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    alert = db.query(QualityAlert).filter(QualityAlert.company_id == company.id, QualityAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "acknowledged"
    alert.acknowledged_by_id = user.id
    db.commit()
    log_activity(db, "quality_alert_acknowledged", user_id=user.id, details={"alert_id": alert.id}, ip_address=get_client_ip(request))
    return {"ok": True}


@router.get("/corrective-actions", response_model=CapaListResponse)
def list_capas(
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.view")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    q = (
        db.query(CorrectiveAction)
        .options(joinedload(CorrectiveAction.inspection).joinedload(QualityInspection.product), joinedload(CorrectiveAction.assigned_to))
        .filter(CorrectiveAction.company_id == company.id)
    )
    if status:
        q = q.filter(CorrectiveAction.status == status)
    capas = q.order_by(CorrectiveAction.id.desc()).all()
    return CapaListResponse(items=[_capa_list_item(c) for c in capas], total=len(capas))


@router.post("/corrective-actions", response_model=CapaResponse)
def create_capa(
    body: CapaCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.manage_capa")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    if body.action_type not in CAPA_ACTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid action type")
    insp = _get_inspection(db, company.id, body.inspection_id)
    if insp.status not in ("failed", "waived"):
        raise HTTPException(status_code=400, detail="CAPA requires failed or waived inspection")
    capa = CorrectiveAction(
        company_id=company.id,
        capa_number=generate_capa_number(db, company.id, settings.capa_number_prefix),
        inspection_id=insp.id,
        title=body.title,
        description=body.description,
        action_type=body.action_type,
        assigned_to_id=body.assigned_to_id,
        due_date=body.due_date,
        corrective_steps=body.corrective_steps,
        created_by_id=user.id,
    )
    db.add(capa)
    db.commit()
    capa = (
        db.query(CorrectiveAction)
        .options(joinedload(CorrectiveAction.inspection), joinedload(CorrectiveAction.assigned_to), joinedload(CorrectiveAction.closed_by))
        .filter(CorrectiveAction.id == capa.id)
        .first()
    )
    log_activity(db, "capa_created", user_id=user.id, details={"capa_id": capa.id}, ip_address=get_client_ip(request))
    return _capa_response(capa)


@router.get("/corrective-actions/{capa_id}", response_model=CapaResponse)
def get_capa(capa_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("quality.view"))):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    capa = (
        db.query(CorrectiveAction)
        .options(joinedload(CorrectiveAction.inspection), joinedload(CorrectiveAction.assigned_to), joinedload(CorrectiveAction.closed_by))
        .filter(CorrectiveAction.company_id == company.id, CorrectiveAction.id == capa_id)
        .first()
    )
    if not capa:
        raise HTTPException(status_code=404, detail="CAPA not found")
    return _capa_response(capa)


@router.put("/corrective-actions/{capa_id}", response_model=CapaResponse)
def update_capa(
    capa_id: int,
    body: CapaUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("quality.manage_capa")),
):
    company = get_current_company(db, user)
    settings = get_quality_settings(db, company)
    _require_enabled(settings)
    capa = (
        db.query(CorrectiveAction)
        .options(joinedload(CorrectiveAction.inspection), joinedload(CorrectiveAction.assigned_to), joinedload(CorrectiveAction.closed_by))
        .filter(CorrectiveAction.company_id == company.id, CorrectiveAction.id == capa_id)
        .first()
    )
    if not capa:
        raise HTTPException(status_code=404, detail="CAPA not found")
    data = body.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    if new_status:
        if new_status not in CAPA_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid CAPA status")
        if new_status == "closed":
            notes = data.get("verification_notes") or capa.verification_notes
            if not notes or not str(notes).strip():
                raise HTTPException(status_code=400, detail="Verification notes required to close CAPA")
            capa.closed_by_id = user.id
            capa.closed_at = _utcnow()
        capa.status = new_status
    for key, value in data.items():
        setattr(capa, key, value)
    db.commit()
    db.refresh(capa)
    if capa.status == "closed":
        log_activity(db, "capa_closed", user_id=user.id, details={"capa_id": capa.id}, ip_address=get_client_ip(request))
    return _capa_response(capa)
