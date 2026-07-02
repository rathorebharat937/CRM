"""Manufacturing / MRP API."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from auth_utils import get_client_ip, get_db, require_permission
from manufacturing_config import (
    BOM_STATUSES,
    DEFAULT_CHECKLIST,
    QC_STATUSES,
    STATUS_TRANSITIONS,
    WO_PRIORITIES,
    WO_STATUSES,
)
from manufacturing_schemas import (
    BomCreateRequest,
    BomExplodeLine,
    BomExplodeResponse,
    BomLineResponse,
    BomListItem,
    BomListResponse,
    BomResponse,
    BomUpdateRequest,
    FinishedGoodsReceiptRequest,
    ManufacturingDashboardResponse,
    ManufacturingSettingsResponse,
    ManufacturingSettingsUpdateRequest,
    MaterialIssueLine,
    MaterialIssueRequest,
    MaterialPlanLine,
    QualityInspectionListItem,
    QualityInspectionListResponse,
    QualityInspectionResponse,
    QualityInspectionSubmitRequest,
    QualityInspectionSummary,
    ReceiptLine,
    WorkOrderCreateRequest,
    WorkOrderFromSalesOrderRequest,
    WorkOrderListItem,
    WorkOrderListResponse,
    WorkOrderResponse,
    WorkOrderStatusRequest,
)
from models import (
    BomHeader,
    BomLine,
    Company,
    ManufacturingSettings,
    Product,
    QualityInspection,
    SalesOrder,
    SalesOrderLineItem,
    User,
    WorkOrder,
    WorkOrderMaterialIssue,
    WorkOrderMaterialPlan,
    WorkOrderReceipt,
)
from routers.inventory_router import _apply_movement

router = APIRouter(prefix="/manufacturing", tags=["manufacturing"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)


def _get_company(db: Session) -> Company:
    company = db.query(Company).first()
    if not company:
        raise HTTPException(status_code=400, detail="Company must be configured")
    return company


def _get_settings(db: Session, company: Company) -> ManufacturingSettings:
    settings = (
        db.query(ManufacturingSettings)
        .filter(ManufacturingSettings.company_id == company.id)
        .first()
    )
    if settings:
        return settings
    settings = ManufacturingSettings(
        company_id=company.id,
        is_enabled=True,
        default_checklist_json=DEFAULT_CHECKLIST,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _require_enabled(settings: ManufacturingSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="Manufacturing is not enabled")


def _settings_response(settings: ManufacturingSettings) -> ManufacturingSettingsResponse:
    checklist = settings.default_checklist_json or DEFAULT_CHECKLIST
    return ManufacturingSettingsResponse(
        is_enabled=settings.is_enabled,
        work_order_prefix=settings.work_order_prefix,
        auto_reserve_materials_on_release=settings.auto_reserve_materials_on_release,
        require_qc_before_receipt=settings.require_qc_before_receipt,
        default_scrap_pct=_float(settings.default_scrap_pct),
        allow_negative_issue=settings.allow_negative_issue,
        default_checklist_json=checklist,
    )


def _generate_wo_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    like = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(WorkOrder.id))
        .filter(WorkOrder.company_id == company_id, WorkOrder.work_order_number.like(like))
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _generate_qc_number(db: Session, company_id: int) -> str:
    year = _utcnow().year
    prefix = "QC"
    like = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(QualityInspection.id))
        .filter(
            QualityInspection.company_id == company_id,
            QualityInspection.inspection_number.like(like),
        )
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _product_unit_cost(product: Product) -> float:
    price = product.offer_price or product.total_price or product.unit_valuation
    return _float(price)


def _get_bom(db: Session, company_id: int, bom_id: int) -> BomHeader:
    bom = (
        db.query(BomHeader)
        .options(
            joinedload(BomHeader.lines).joinedload(BomLine.component_product),
            joinedload(BomHeader.product),
        )
        .filter(BomHeader.company_id == company_id, BomHeader.id == bom_id)
        .first()
    )
    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")
    return bom


def _get_active_bom(db: Session, company_id: int, product_id: int) -> BomHeader | None:
    product = db.query(Product).filter(Product.company_id == company_id, Product.id == product_id).first()
    if product and product.default_bom_id:
        bom = _get_bom(db, company_id, product.default_bom_id)
        if bom.status == "active":
            return bom
    return (
        db.query(BomHeader)
        .options(joinedload(BomHeader.lines).joinedload(BomLine.component_product))
        .filter(
            BomHeader.company_id == company_id,
            BomHeader.product_id == product_id,
            BomHeader.status == "active",
        )
        .order_by(BomHeader.id.desc())
        .first()
    )


def _bom_line_cost(line: BomLine) -> float:
    comp = line.component_product
    if not comp:
        return 0
    return _product_unit_cost(comp) * _float(line.quantity)


def _bom_lines_response(bom: BomHeader) -> list[BomLineResponse]:
    lines = []
    for line in bom.lines:
        comp = line.component_product
        lines.append(
            BomLineResponse(
                id=line.id,
                component_product_id=line.component_product_id,
                component_product_name=comp.name if comp else "—",
                quantity=_float(line.quantity),
                scrap_pct=_float(line.scrap_pct),
                sort_order=line.sort_order,
                notes=line.notes,
                on_hand=_float(comp.on_hand_quantity) if comp else 0,
                unit_cost=_product_unit_cost(comp) if comp else 0,
            )
        )
    return lines


def _bom_response(bom: BomHeader) -> BomResponse:
    product = bom.product
    lines = _bom_lines_response(bom)
    return BomResponse(
        id=bom.id,
        product_id=bom.product_id,
        product_name=product.name if product else "—",
        name=bom.name,
        version=bom.version,
        status=bom.status,
        output_qty=_float(bom.output_qty),
        output_uom=bom.output_uom,
        notes=bom.notes,
        lines=lines,
        estimated_batch_cost=sum(_bom_line_cost(line) for line in bom.lines),
        created_at=bom.created_at,
        updated_at=bom.updated_at,
    )


def _check_circular_bom(db: Session, company_id: int, finished_product_id: int, component_ids: list[int]) -> None:
    if finished_product_id in component_ids:
        raise HTTPException(status_code=400, detail="BOM cannot include the finished product as a component")

    visited: set[int] = set()

    def _descendants(product_id: int) -> set[int]:
        if product_id in visited:
            return set()
        visited.add(product_id)
        bom = _get_active_bom(db, company_id, product_id)
        if not bom:
            return set()
        result = set()
        for line in bom.lines:
            result.add(line.component_product_id)
            result |= _descendants(line.component_product_id)
        return result

    for comp_id in component_ids:
        if finished_product_id in _descendants(comp_id):
            raise HTTPException(status_code=400, detail="Circular BOM reference detected")


def _scale_required_qty(planned_qty: float, bom: BomHeader, line: BomLine) -> float:
    output_qty = _float(bom.output_qty) or 1
    scrap = 1 + _float(line.scrap_pct) / 100
    return (planned_qty / output_qty) * _float(line.quantity) * scrap


def _explode_lines(
    db: Session,
    bom: BomHeader,
    batch_qty: float,
) -> list[BomExplodeLine]:
    result = []
    for line in bom.lines:
        comp = line.component_product or db.query(Product).get(line.component_product_id)
        required = _scale_required_qty(batch_qty, bom, line)
        on_hand = _float(comp.on_hand_quantity) if comp else 0
        result.append(
            BomExplodeLine(
                component_product_id=line.component_product_id,
                component_product_name=comp.name if comp else "—",
                required_qty=round(required, 4),
                on_hand=on_hand,
                shortage=round(max(0, required - on_hand), 4),
                unit=comp.unit if comp else "Unit",
            )
        )
    return result


def _build_material_plans(db: Session, wo: WorkOrder, bom: BomHeader) -> None:
    db.query(WorkOrderMaterialPlan).filter(WorkOrderMaterialPlan.work_order_id == wo.id).delete()
    for line in bom.lines:
        comp = line.component_product or db.query(Product).get(line.component_product_id)
        db.add(
            WorkOrderMaterialPlan(
                work_order_id=wo.id,
                component_product_id=line.component_product_id,
                required_qty=Decimal(str(_scale_required_qty(_float(wo.planned_qty), bom, line))),
                issued_qty=Decimal("0"),
                unit=comp.unit if comp else "Unit",
            )
        )


def _get_work_order(db: Session, company_id: int, wo_id: int) -> WorkOrder:
    wo = (
        db.query(WorkOrder)
        .options(
            joinedload(WorkOrder.product),
            joinedload(WorkOrder.bom),
            joinedload(WorkOrder.sales_order),
            joinedload(WorkOrder.assigned_to),
            joinedload(WorkOrder.material_plans).joinedload(WorkOrderMaterialPlan.component_product),
            joinedload(WorkOrder.material_issues).joinedload(WorkOrderMaterialIssue.component_product),
            joinedload(WorkOrder.material_issues).joinedload(WorkOrderMaterialIssue.issued_by),
            joinedload(WorkOrder.receipts).joinedload(WorkOrderReceipt.received_by),
            joinedload(WorkOrder.quality_inspections).joinedload(QualityInspection.inspected_by),
            joinedload(WorkOrder.quality_inspections).joinedload(QualityInspection.inspection_point),
        )
        .filter(WorkOrder.company_id == company_id, WorkOrder.id == wo_id)
        .first()
    )
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    return wo


def _material_plan_lines(wo: WorkOrder) -> list[MaterialPlanLine]:
    lines = []
    for plan in wo.material_plans:
        comp = plan.component_product
        required = _float(plan.required_qty)
        issued = _float(plan.issued_qty)
        on_hand = _float(comp.on_hand_quantity) if comp else 0
        shortage = max(0, required - issued) if required > issued else max(0, required - on_hand)
        lines.append(
            MaterialPlanLine(
                id=plan.id,
                component_product_id=plan.component_product_id,
                component_product_name=comp.name if comp else "—",
                required_qty=required,
                issued_qty=issued,
                shortage=round(shortage, 4),
                unit=plan.unit,
            )
        )
    return lines


def _wo_list_item(wo: WorkOrder) -> WorkOrderListItem:
    return WorkOrderListItem(
        id=wo.id,
        work_order_number=wo.work_order_number,
        product_id=wo.product_id,
        product_name=wo.product.name if wo.product else "—",
        status=wo.status,
        planned_qty=_float(wo.planned_qty),
        completed_qty=_float(wo.completed_qty),
        planned_start=wo.planned_start,
        planned_end=wo.planned_end,
        priority=wo.priority,
        sales_order_number=wo.sales_order.order_number if wo.sales_order else None,
        assigned_to_name=wo.assigned_to.name if wo.assigned_to else None,
    )


def _wo_response(wo: WorkOrder) -> WorkOrderResponse:
    return WorkOrderResponse(
        id=wo.id,
        work_order_number=wo.work_order_number,
        product_id=wo.product_id,
        product_name=wo.product.name if wo.product else "—",
        bom_id=wo.bom_id,
        bom_name=wo.bom.name if wo.bom else None,
        sales_order_id=wo.sales_order_id,
        sales_order_number=wo.sales_order.order_number if wo.sales_order else None,
        sales_order_line_id=wo.sales_order_line_id,
        project_id=wo.project_id,
        status=wo.status,
        planned_qty=_float(wo.planned_qty),
        completed_qty=_float(wo.completed_qty),
        scrap_qty=_float(wo.scrap_qty),
        planned_start=wo.planned_start,
        planned_end=wo.planned_end,
        actual_start=wo.actual_start,
        actual_end=wo.actual_end,
        assigned_to_id=wo.assigned_to_id,
        assigned_to_name=wo.assigned_to.name if wo.assigned_to else None,
        priority=wo.priority,
        notes=wo.notes,
        material_plans=_material_plan_lines(wo),
        material_issues=[
            MaterialIssueLine(
                id=i.id,
                component_product_id=i.component_product_id,
                component_product_name=i.component_product.name if i.component_product else "—",
                quantity=_float(i.quantity),
                issued_at=i.issued_at,
                issued_by_name=i.issued_by.name if i.issued_by else "—",
            )
            for i in wo.material_issues
        ],
        receipts=[
            ReceiptLine(
                id=r.id,
                quantity=_float(r.quantity),
                received_at=r.received_at,
                received_by_name=r.received_by.name if r.received_by else "—",
            )
            for r in wo.receipts
        ],
        quality_inspections=[
            QualityInspectionSummary(
                id=q.id,
                inspection_number=q.inspection_number,
                status=q.status,
                inspected_at=q.inspected_at,
                inspected_by_name=q.inspected_by.name if q.inspected_by else None,
            )
            for q in wo.quality_inspections
        ],
        created_at=wo.created_at,
    )


def _issue_component_stock(
    db: Session,
    product: Product,
    user: User,
    qty: float,
    wo_number: str,
    allow_negative: bool,
) -> int | None:
    if not product.inventory_tracked:
        return None
    movement = _apply_movement(
        db,
        product,
        user,
        "sale",
        qty,
        _float(product.unit_valuation),
        _utcnow(),
        reason="internal_consumption",
        notes=f"Material issue for {wo_number}",
        reference_number=wo_number,
        reference_type="work_order",
        source_module="manufacturing",
        allow_negative=allow_negative,
    )
    return movement.id


def _receive_fg_stock(
    db: Session,
    product: Product,
    user: User,
    qty: float,
    wo_number: str,
) -> int | None:
    if not product.inventory_tracked:
        return None
    movement = _apply_movement(
        db,
        product,
        user,
        "adjustment",
        qty,
        _float(product.unit_valuation),
        _utcnow(),
        adjustment_direction="in",
        reason="other",
        notes=f"Production receipt {wo_number}",
        reference_number=wo_number,
        reference_type="work_order",
        source_module="manufacturing",
    )
    return movement.id


def _shortages_for_company(db: Session, company_id: int) -> list[dict]:
    open_statuses = ["released", "in_progress", "qc_pending", "planned"]
    plans = (
        db.query(WorkOrderMaterialPlan)
        .join(WorkOrder, WorkOrder.id == WorkOrderMaterialPlan.work_order_id)
        .filter(WorkOrder.company_id == company_id, WorkOrder.status.in_(open_statuses))
        .all()
    )
    required_by_product: dict[int, float] = defaultdict(float)
    for plan in plans:
        required_by_product[plan.component_product_id] += _float(plan.required_qty) - _float(plan.issued_qty)

    shortages = []
    for product_id, required in required_by_product.items():
        if required <= 0:
            continue
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            continue
        on_hand = _float(product.on_hand_quantity)
        if required > on_hand:
            shortages.append(
                {
                    "product_id": product_id,
                    "product_name": product.name,
                    "required_qty": round(required, 4),
                    "on_hand": on_hand,
                    "shortage": round(required - on_hand, 4),
                    "unit": product.unit,
                }
            )
    shortages.sort(key=lambda x: x["shortage"], reverse=True)
    return shortages


@router.get("/dashboard", response_model=ManufacturingDashboardResponse)
def manufacturing_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    today = _utcnow().date()
    open_statuses = ["draft", "planned", "released", "in_progress", "qc_pending"]
    open_count = (
        db.query(func.count(WorkOrder.id))
        .filter(WorkOrder.company_id == company.id, WorkOrder.status.in_(open_statuses))
        .scalar()
    )
    overdue = (
        db.query(func.count(WorkOrder.id))
        .filter(
            WorkOrder.company_id == company.id,
            WorkOrder.status.in_(open_statuses),
            WorkOrder.planned_end.isnot(None),
            WorkOrder.planned_end < today,
        )
        .scalar()
    )
    shortages = _shortages_for_company(db, company.id)
    since = _utcnow() - timedelta(days=7)
    fg_7d = (
        db.query(func.coalesce(func.sum(WorkOrderReceipt.quantity), 0))
        .join(WorkOrder, WorkOrder.id == WorkOrderReceipt.work_order_id)
        .filter(WorkOrder.company_id == company.id, WorkOrderReceipt.received_at >= since)
        .scalar()
    )
    recent = (
        db.query(WorkOrder)
        .options(joinedload(WorkOrder.product), joinedload(WorkOrder.sales_order), joinedload(WorkOrder.assigned_to))
        .filter(WorkOrder.company_id == company.id)
        .order_by(WorkOrder.id.desc())
        .limit(10)
        .all()
    )
    return ManufacturingDashboardResponse(
        open_work_orders=int(open_count or 0),
        overdue_work_orders=int(overdue or 0),
        shortages_count=len(shortages),
        fg_produced_7d=_float(fg_7d),
        recent_work_orders=[_wo_list_item(wo) for wo in recent],
        critical_shortages=shortages[:10],
    )


@router.get("/settings", response_model=ManufacturingSettingsResponse)
def get_manufacturing_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    return _settings_response(_get_settings(db, company))


@router.put("/settings", response_model=ManufacturingSettingsResponse)
def update_manufacturing_settings(
    body: ManufacturingSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.manage_settings")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    log_activity(
        db,
        "manufacturing_settings_updated",
        user_id=user.id,
        details={"is_enabled": settings.is_enabled},
        ip_address=get_client_ip(request),
    )
    return _settings_response(settings)


@router.get("/boms", response_model=BomListResponse)
def list_boms(
    status: str | None = None,
    product_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    q = (
        db.query(BomHeader)
        .options(joinedload(BomHeader.product), joinedload(BomHeader.lines))
        .filter(BomHeader.company_id == company.id)
    )
    if status:
        q = q.filter(BomHeader.status == status)
    if product_id:
        q = q.filter(BomHeader.product_id == product_id)
    boms = q.order_by(BomHeader.id.desc()).all()
    items = []
    for bom in boms:
        product = bom.product
        items.append(
            BomListItem(
                id=bom.id,
                product_id=bom.product_id,
                product_name=product.name if product else "—",
                name=bom.name,
                version=bom.version,
                status=bom.status,
                output_qty=_float(bom.output_qty),
                output_uom=bom.output_uom,
                line_count=len(bom.lines),
                estimated_batch_cost=sum(_bom_line_cost(line) for line in bom.lines),
            )
        )
    return BomListResponse(items=items, total=len(items))


@router.post("/boms", response_model=BomResponse)
def create_bom(
    body: BomCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.manage_bom")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    product = db.query(Product).filter(Product.company_id == company.id, Product.id == body.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_manufactured:
        raise HTTPException(status_code=400, detail="Product must be marked as manufactured")
    if not body.lines:
        raise HTTPException(status_code=400, detail="BOM requires at least one component line")

    component_ids = [line.component_product_id for line in body.lines]
    _check_circular_bom(db, company.id, body.product_id, component_ids)

    bom = BomHeader(
        company_id=company.id,
        product_id=body.product_id,
        name=body.name,
        version=body.version,
        output_qty=Decimal(str(body.output_qty)),
        output_uom=body.output_uom,
        notes=body.notes,
        created_by_id=user.id,
    )
    db.add(bom)
    db.flush()
    for idx, line in enumerate(body.lines):
        db.add(
            BomLine(
                bom_id=bom.id,
                component_product_id=line.component_product_id,
                quantity=Decimal(str(line.quantity)),
                scrap_pct=Decimal(str(line.scrap_pct)),
                sort_order=line.sort_order or idx,
                notes=line.notes,
            )
        )
    db.commit()
    bom = _get_bom(db, company.id, bom.id)
    log_activity(db, "bom_created", user_id=user.id, details={"bom_id": bom.id, "product_id": bom.product_id}, ip_address=get_client_ip(request))
    return _bom_response(bom)


@router.get("/boms/{bom_id}", response_model=BomResponse)
def get_bom(
    bom_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    return _bom_response(_get_bom(db, company.id, bom_id))


@router.put("/boms/{bom_id}", response_model=BomResponse)
def update_bom(
    bom_id: int,
    body: BomUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.manage_bom")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    bom = _get_bom(db, company.id, bom_id)
    if bom.status == "archived":
        raise HTTPException(status_code=400, detail="Archived BOM cannot be edited")

    data = body.model_dump(exclude_unset=True)
    lines = data.pop("lines", None)
    for key, value in data.items():
        if value is not None:
            if key == "output_qty":
                setattr(bom, key, Decimal(str(value)))
            else:
                setattr(bom, key, value)

    if lines is not None:
        if not lines:
            raise HTTPException(status_code=400, detail="BOM requires at least one component line")
        component_ids = [line["component_product_id"] for line in lines]
        _check_circular_bom(db, company.id, bom.product_id, component_ids)
        db.query(BomLine).filter(BomLine.bom_id == bom.id).delete()
        for idx, line in enumerate(lines):
            db.add(
                BomLine(
                    bom_id=bom.id,
                    component_product_id=line["component_product_id"],
                    quantity=Decimal(str(line["quantity"])),
                    scrap_pct=Decimal(str(line.get("scrap_pct", 0))),
                    sort_order=line.get("sort_order", idx),
                    notes=line.get("notes"),
                )
            )

    db.commit()
    bom = _get_bom(db, company.id, bom.id)
    log_activity(db, "bom_updated", user_id=user.id, details={"bom_id": bom.id}, ip_address=get_client_ip(request))
    return _bom_response(bom)


@router.post("/boms/{bom_id}/activate", response_model=BomResponse)
def activate_bom(
    bom_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.manage_bom")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    bom = _get_bom(db, company.id, bom_id)
    if not bom.lines:
        raise HTTPException(status_code=400, detail="BOM requires at least one component line")

    (
        db.query(BomHeader)
        .filter(
            BomHeader.company_id == company.id,
            BomHeader.product_id == bom.product_id,
            BomHeader.status == "active",
            BomHeader.id != bom.id,
        )
        .update({"status": "archived"})
    )
    bom.status = "active"
    product = db.query(Product).filter(Product.id == bom.product_id).first()
    if product:
        product.default_bom_id = bom.id
    db.commit()
    bom = _get_bom(db, company.id, bom.id)
    log_activity(db, "bom_activated", user_id=user.id, details={"bom_id": bom.id}, ip_address=get_client_ip(request))
    return _bom_response(bom)


@router.get("/boms/{bom_id}/explode", response_model=BomExplodeResponse)
def explode_bom(
    bom_id: int,
    qty: float = Query(default=1, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    bom = _get_bom(db, company.id, bom_id)
    product = bom.product
    return BomExplodeResponse(
        bom_id=bom.id,
        product_name=product.name if product else "—",
        batch_qty=qty,
        lines=_explode_lines(db, bom, qty),
    )


@router.get("/work-orders", response_model=WorkOrderListResponse)
def list_work_orders(
    status: str | None = None,
    product_id: int | None = None,
    sales_order_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    q = (
        db.query(WorkOrder)
        .options(joinedload(WorkOrder.product), joinedload(WorkOrder.sales_order), joinedload(WorkOrder.assigned_to))
        .filter(WorkOrder.company_id == company.id)
    )
    if status:
        q = q.filter(WorkOrder.status == status)
    if product_id:
        q = q.filter(WorkOrder.product_id == product_id)
    if sales_order_id:
        q = q.filter(WorkOrder.sales_order_id == sales_order_id)
    orders = q.order_by(WorkOrder.id.desc()).all()
    return WorkOrderListResponse(items=[_wo_list_item(wo) for wo in orders], total=len(orders))


@router.post("/work-orders", response_model=WorkOrderResponse)
def create_work_order(
    body: WorkOrderCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.create_wo")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    if body.status not in WO_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    if body.priority not in WO_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority")

    product = db.query(Product).filter(Product.company_id == company.id, Product.id == body.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_manufactured:
        raise HTTPException(status_code=400, detail="Product must be manufactured")

    bom = None
    if body.bom_id:
        bom = _get_bom(db, company.id, body.bom_id)
        if bom.product_id != body.product_id:
            raise HTTPException(status_code=400, detail="BOM does not match product")
    else:
        bom = _get_active_bom(db, company.id, body.product_id)

    wo = WorkOrder(
        company_id=company.id,
        work_order_number=_generate_wo_number(db, company.id, settings.work_order_prefix),
        product_id=body.product_id,
        bom_id=bom.id if bom else None,
        sales_order_id=body.sales_order_id,
        sales_order_line_id=body.sales_order_line_id,
        project_id=body.project_id,
        status=body.status if body.status in ("draft", "planned") else "draft",
        planned_qty=Decimal(str(body.planned_qty)),
        planned_start=body.planned_start,
        planned_end=body.planned_end,
        assigned_to_id=body.assigned_to_id,
        priority=body.priority,
        notes=body.notes,
        created_by_id=user.id,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    log_activity(
        db,
        "wo_created",
        user_id=user.id,
        details={"work_order_id": wo.id, "number": wo.work_order_number},
        ip_address=get_client_ip(request),
    )
    return _wo_response(_get_work_order(db, company.id, wo.id))


@router.post("/work-orders/from-sales-order/{so_id}", response_model=WorkOrderResponse)
def create_work_order_from_sales_order(
    so_id: int,
    body: WorkOrderFromSalesOrderRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.create_wo")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    so = db.query(SalesOrder).filter(SalesOrder.company_id == company.id, SalesOrder.id == so_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")

    line = (
        db.query(SalesOrderLineItem)
        .filter(SalesOrderLineItem.sales_order_id == so.id, SalesOrderLineItem.id == body.sales_order_line_id)
        .first()
    )
    if not line:
        raise HTTPException(status_code=404, detail="Sales order line not found")
    if not line.product_id:
        raise HTTPException(status_code=400, detail="Line has no linked product")

    product = db.query(Product).filter(Product.id == line.product_id, Product.company_id == company.id).first()
    if not product or not product.is_manufactured:
        raise HTTPException(status_code=400, detail="Line product must be manufactured")

    planned_qty = body.planned_qty if body.planned_qty else _float(line.quantity)
    create_body = WorkOrderCreateRequest(
        product_id=line.product_id,
        planned_qty=planned_qty,
        sales_order_id=so.id,
        sales_order_line_id=line.id,
        planned_start=body.planned_start,
        planned_end=body.planned_end,
        assigned_to_id=body.assigned_to_id,
        priority=body.priority,
        notes=body.notes,
        status="planned",
    )
    return create_work_order(create_body, request, db, user)


@router.get("/work-orders/{wo_id}", response_model=WorkOrderResponse)
def get_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    return _wo_response(_get_work_order(db, company.id, wo_id))


@router.put("/work-orders/{wo_id}/status", response_model=WorkOrderResponse)
def update_work_order_status(
    wo_id: int,
    body: WorkOrderStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.release_wo")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    wo = _get_work_order(db, company.id, wo_id)

    new_status = body.status
    if new_status not in WO_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    allowed = STATUS_TRANSITIONS.get(wo.status, [])
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {wo.status} to {new_status}")

    if new_status == "released":
        bom = wo.bom
        if not bom:
            bom = _get_active_bom(db, company.id, wo.product_id)
        if not bom:
            raise HTTPException(status_code=400, detail="Active BOM required to release work order")
        wo.bom_id = bom.id
        _build_material_plans(db, wo, bom)
        if settings.auto_reserve_materials_on_release:
            pass  # reservation table Phase 2

    if new_status == "in_progress" and not wo.actual_start:
        wo.actual_start = _utcnow()

    if new_status == "qc_pending":
        from services.quality_service import create_wo_final_inspection

        checklist = settings.default_checklist_json or DEFAULT_CHECKLIST
        create_wo_final_inspection(db, company, wo, mfg_checklist=checklist)

    if new_status == "completed":
        if _float(wo.completed_qty) <= 0:
            raise HTTPException(status_code=400, detail="Receive finished goods before completing")
        wo.actual_end = _utcnow()

    if new_status == "cancelled":
        if wo.status == "completed":
            raise HTTPException(status_code=400, detail="Cannot cancel completed work order")

    wo.status = new_status
    if body.notes:
        wo.notes = (wo.notes or "") + f"\n[{new_status}] {body.notes}"

    db.commit()
    log_activity(
        db,
        "wo_status_changed",
        user_id=user.id,
        details={"work_order_id": wo.id, "status": new_status},
        ip_address=get_client_ip(request),
    )
    return _wo_response(_get_work_order(db, company.id, wo.id))


@router.post("/work-orders/{wo_id}/issue", response_model=WorkOrderResponse)
def issue_materials(
    wo_id: int,
    body: MaterialIssueRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.issue_materials")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    wo = _get_work_order(db, company.id, wo_id)

    if wo.status not in ("released", "in_progress"):
        raise HTTPException(status_code=400, detail="Work order must be released or in progress")

    plans_by_product = {p.component_product_id: p for p in wo.material_plans}
    to_issue: list[tuple[int, float]] = []

    if body.issue_all:
        for plan in wo.material_plans:
            remaining = _float(plan.required_qty) - _float(plan.issued_qty)
            if remaining > 0:
                to_issue.append((plan.component_product_id, remaining))
    elif body.lines:
        for line in body.lines:
            pid = int(line["component_product_id"])
            qty = float(line["quantity"])
            if qty <= 0:
                continue
            to_issue.append((pid, qty))
    else:
        raise HTTPException(status_code=400, detail="Provide lines or issue_all")

    for product_id, qty in to_issue:
        plan = plans_by_product.get(product_id)
        if not plan:
            raise HTTPException(status_code=400, detail=f"No material plan for product {product_id}")
        remaining_allowed = _float(plan.required_qty) - _float(plan.issued_qty)
        if qty > remaining_allowed + 0.0001 and not settings.allow_negative_issue:
            raise HTTPException(
                status_code=400,
                detail=f"Issue qty exceeds required for product {product_id}",
            )
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Component product not found")
        movement_id = _issue_component_stock(
            db,
            product,
            user,
            qty,
            wo.work_order_number,
            settings.allow_negative_issue,
        )
        db.add(
            WorkOrderMaterialIssue(
                work_order_id=wo.id,
                component_product_id=product_id,
                quantity=Decimal(str(qty)),
                stock_movement_id=movement_id,
                issued_by_id=user.id,
            )
        )
        plan.issued_qty = Decimal(str(_float(plan.issued_qty) + qty))

    if wo.status == "released":
        wo.status = "in_progress"
        if not wo.actual_start:
            wo.actual_start = _utcnow()

    db.commit()
    log_activity(
        db,
        "wo_material_issued",
        user_id=user.id,
        details={"work_order_id": wo.id, "lines": len(to_issue)},
        ip_address=get_client_ip(request),
    )
    return _wo_response(_get_work_order(db, company.id, wo.id))


@router.post("/work-orders/{wo_id}/receive", response_model=WorkOrderResponse)
def receive_finished_goods(
    wo_id: int,
    body: FinishedGoodsReceiptRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.receive_fg")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    wo = _get_work_order(db, company.id, wo_id)

    if wo.status in ("cancelled", "completed"):
        raise HTTPException(status_code=400, detail="Cannot receive on cancelled or completed work order")

    if settings.require_qc_before_receipt:
        from services.quality_service import get_quality_settings, wo_final_blocked_by_fail

        qsettings = get_quality_settings(db, company)
        if wo_final_blocked_by_fail(wo, qsettings):
            raise HTTPException(status_code=400, detail="QC failed — finished goods receipt blocked")
        passed = any(q.status in ("passed", "waived") for q in wo.quality_inspections)
        if wo.status == "qc_pending" and not passed:
            raise HTTPException(status_code=400, detail="QC must pass before receiving finished goods")
        if wo.status not in ("qc_pending", "in_progress", "released") and not passed:
            raise HTTPException(status_code=400, detail="QC must pass before receiving finished goods")

    remaining = _float(wo.planned_qty) - _float(wo.completed_qty)
    if body.quantity + body.scrap_qty > remaining + 0.0001:
        raise HTTPException(status_code=400, detail="Receive qty exceeds remaining planned quantity")

    product = wo.product
    if not product:
        raise HTTPException(status_code=400, detail="Work order product missing")

    movement_id = _receive_fg_stock(db, product, user, body.quantity, wo.work_order_number)
    db.add(
        WorkOrderReceipt(
            work_order_id=wo.id,
            quantity=Decimal(str(body.quantity)),
            stock_movement_id=movement_id,
            received_by_id=user.id,
        )
    )
    wo.completed_qty = Decimal(str(_float(wo.completed_qty) + body.quantity))
    wo.scrap_qty = Decimal(str(_float(wo.scrap_qty) + body.scrap_qty))

    if _float(wo.completed_qty) >= _float(wo.planned_qty):
        wo.status = "completed"
        wo.actual_end = _utcnow()

    db.commit()
    log_activity(
        db,
        "wo_completed",
        user_id=user.id,
        details={"work_order_id": wo.id, "quantity": body.quantity},
        ip_address=get_client_ip(request),
    )
    return _wo_response(_get_work_order(db, company.id, wo.id))


@router.get("/quality", response_model=QualityInspectionListResponse)
def list_quality_inspections(
    status: str | None = Query(default="pending"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    q = (
        db.query(QualityInspection)
        .options(
            joinedload(QualityInspection.work_order).joinedload(WorkOrder.product),
            joinedload(QualityInspection.inspected_by),
        )
        .filter(QualityInspection.company_id == company.id)
    )
    if status:
        q = q.filter(QualityInspection.status == status)
    items_db = q.order_by(QualityInspection.id.desc()).all()
    items = []
    for insp in items_db:
        wo = insp.work_order
        items.append(
            QualityInspectionListItem(
                id=insp.id,
                inspection_number=insp.inspection_number,
                work_order_id=insp.work_order_id,
                work_order_number=wo.work_order_number if wo else "—",
                product_name=wo.product.name if wo and wo.product else "—",
                status=insp.status,
                inspected_at=insp.inspected_at,
                inspected_by_name=insp.inspected_by.name if insp.inspected_by else None,
            )
        )
    return QualityInspectionListResponse(items=items, total=len(items))


@router.get("/quality/{inspection_id}", response_model=QualityInspectionResponse)
def get_quality_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    insp = (
        db.query(QualityInspection)
        .options(
            joinedload(QualityInspection.work_order).joinedload(WorkOrder.product),
            joinedload(QualityInspection.inspected_by),
        )
        .filter(QualityInspection.company_id == company.id, QualityInspection.id == inspection_id)
        .first()
    )
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    wo = insp.work_order
    return QualityInspectionResponse(
        id=insp.id,
        inspection_number=insp.inspection_number,
        work_order_id=insp.work_order_id,
        work_order_number=wo.work_order_number if wo else "—",
        product_name=wo.product.name if wo and wo.product else "—",
        status=insp.status,
        checklist_json=insp.checklist_json or [],
        notes=insp.notes,
        inspected_by_id=insp.inspected_by_id,
        inspected_by_name=insp.inspected_by.name if insp.inspected_by else None,
        inspected_at=insp.inspected_at,
    )


@router.put("/quality/{inspection_id}", response_model=QualityInspectionResponse)
def submit_quality_inspection(
    inspection_id: int,
    body: QualityInspectionSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing.quality")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    if body.status not in QC_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid QC status")
    if body.status == "waived":
        raise HTTPException(status_code=403, detail="QC waiver requires manager permission")

    insp = (
        db.query(QualityInspection)
        .options(joinedload(QualityInspection.work_order).joinedload(WorkOrder.product))
        .filter(QualityInspection.company_id == company.id, QualityInspection.id == inspection_id)
        .first()
    )
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if insp.status != "pending":
        raise HTTPException(status_code=400, detail="Inspection already submitted")

    from services.quality_service import get_quality_settings, submit_inspection

    qsettings = get_quality_settings(db, company)
    if qsettings.is_enabled:
        try:
            submit_inspection(db, company, insp, user, body.checklist_json, body.notes, body.status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        if body.status not in QC_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid QC status")
        if body.status == "waived":
            raise HTTPException(status_code=403, detail="QC waiver requires manager permission")
        insp.status = body.status
        insp.checklist_json = body.checklist_json
        insp.notes = body.notes
        insp.inspected_by_id = user.id
        insp.inspected_at = _utcnow()

    db.commit()
    log_activity(
        db,
        "wo_qc_submitted",
        user_id=user.id,
        details={"inspection_id": insp.id, "status": body.status},
        ip_address=get_client_ip(request),
    )
    wo = insp.work_order
    return QualityInspectionResponse(
        id=insp.id,
        inspection_number=insp.inspection_number,
        work_order_id=insp.work_order_id,
        work_order_number=wo.work_order_number if wo else "—",
        product_name=wo.product.name if wo and wo.product else "—",
        status=insp.status,
        checklist_json=insp.checklist_json or [],
        notes=insp.notes,
        inspected_by_id=insp.inspected_by_id,
        inspected_by_name=user.name,
        inspected_at=insp.inspected_at,
    )
