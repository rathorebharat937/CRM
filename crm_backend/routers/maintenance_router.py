"""Maintenance / CMMS API."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from auth_utils import get_client_ip, get_db, require_permission
from maintenance_config import (
    ASSET_CRITICALITIES,
    ASSET_STATUSES,
    DEFAULT_ASSET_CODE_PREFIX,
    DEFAULT_NOTIFY_ROLES,
    DEFAULT_PM_INTERVAL_DAYS,
    DEFAULT_WORK_ORDER_PREFIX,
    MWO_PRIORITIES,
    MWO_STATUS_TRANSITIONS,
    MWO_TYPES,
    OPEN_BREAKDOWN_STATUSES,
    OPEN_MWO_STATUSES,
    SEED_ASSET_CATEGORIES,
)
from maintenance_schemas import (
    AssetCategoryCreateRequest,
    AssetCategoryResponse,
    AssetCategoryUpdateRequest,
    AssetCreateRequest,
    AssetHistoryItem,
    AssetHistoryResponse,
    AssetListItem,
    AssetListResponse,
    AssetResponse,
    AssetUpdateRequest,
    MaintenanceDashboardResponse,
    MaintenanceSettingsResponse,
    MaintenanceSettingsUpdateRequest,
    MwoCompleteRequest,
    MwoCreateRequest,
    MwoIssuePartsRequest,
    MwoListItem,
    MwoListResponse,
    MwoPartLine,
    MwoResponse,
    MwoStatusUpdateRequest,
    PmGenerateRequest,
    PmGenerateResponse,
    PmScheduleItem,
    PmScheduleResponse,
)
from models import (
    Company,
    MaintenanceAsset,
    MaintenanceAssetCategory,
    MaintenanceSettings,
    MaintenanceWoPart,
    MaintenanceWorkOrder,
    Notification,
    Product,
    User,
)
from routers.inventory_router import _apply_movement
from services.notification_service import notify_role

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)


def _get_company(db: Session) -> Company:
    company = db.query(Company).first()
    if not company:
        raise HTTPException(status_code=400, detail="Company must be configured")
    return company


def _get_settings(db: Session, company: Company) -> MaintenanceSettings:
    settings = db.query(MaintenanceSettings).filter(MaintenanceSettings.company_id == company.id).first()
    if settings:
        return settings
    settings = MaintenanceSettings(
        company_id=company.id,
        is_enabled=True,
        notify_roles_json=DEFAULT_NOTIFY_ROLES,
        default_pm_interval_days=DEFAULT_PM_INTERVAL_DAYS,
        work_order_prefix=DEFAULT_WORK_ORDER_PREFIX,
        asset_code_prefix=DEFAULT_ASSET_CODE_PREFIX,
    )
    db.add(settings)
    db.flush()
    return settings


def _require_enabled(settings: MaintenanceSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="Maintenance module is not enabled")


def _settings_response(settings: MaintenanceSettings) -> MaintenanceSettingsResponse:
    return MaintenanceSettingsResponse(
        is_enabled=settings.is_enabled,
        work_order_prefix=settings.work_order_prefix or DEFAULT_WORK_ORDER_PREFIX,
        asset_code_prefix=settings.asset_code_prefix or DEFAULT_ASSET_CODE_PREFIX,
        default_pm_interval_days=int(settings.default_pm_interval_days or DEFAULT_PM_INTERVAL_DAYS),
        critical_downtime_alert_hours=int(settings.critical_downtime_alert_hours or 4),
        auto_deduct_spare_parts=bool(settings.auto_deduct_spare_parts),
        allow_negative_spare_parts=bool(settings.allow_negative_spare_parts),
        notify_roles_json=settings.notify_roles_json or [],
    )


def _pm_interval(asset: MaintenanceAsset, settings: MaintenanceSettings) -> int:
    if asset.pm_interval_days:
        return int(asset.pm_interval_days)
    return int(settings.default_pm_interval_days or DEFAULT_PM_INTERVAL_DAYS)


def _recalc_next_pm(asset: MaintenanceAsset, settings: MaintenanceSettings) -> None:
    interval = _pm_interval(asset, settings)
    base = asset.last_service_date or _utcnow().date()
    asset.next_pm_due_date = base + timedelta(days=interval)


def _generate_asset_code(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    pattern = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(MaintenanceAsset.id))
        .filter(MaintenanceAsset.company_id == company_id, MaintenanceAsset.asset_code.like(pattern))
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _generate_mwo_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    pattern = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(MaintenanceWorkOrder.id))
        .filter(MaintenanceWorkOrder.company_id == company_id, MaintenanceWorkOrder.work_order_number.like(pattern))
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _asset_list_item(asset: MaintenanceAsset, today: date | None = None) -> AssetListItem:
    today = today or _utcnow().date()
    pm_overdue = bool(asset.next_pm_due_date and asset.next_pm_due_date < today and asset.status != "retired")
    return AssetListItem(
        id=asset.id,
        asset_code=asset.asset_code,
        name=asset.name,
        category_id=asset.category_id,
        category_name=asset.category.name if asset.category else None,
        status=asset.status,
        criticality=asset.criticality,
        location_notes=asset.location_notes,
        next_pm_due_date=asset.next_pm_due_date,
        last_service_date=asset.last_service_date,
        pm_overdue=pm_overdue,
    )


def _mwo_list_item(mwo: MaintenanceWorkOrder) -> MwoListItem:
    asset = mwo.asset
    return MwoListItem(
        id=mwo.id,
        work_order_number=mwo.work_order_number,
        asset_id=mwo.asset_id,
        asset_code=asset.asset_code if asset else None,
        asset_name=asset.name if asset else None,
        type=mwo.type,
        priority=mwo.priority,
        status=mwo.status,
        title=mwo.title,
        reported_at=mwo.reported_at,
        downtime_minutes=mwo.downtime_minutes,
        assigned_to_name=mwo.assigned_to.name if mwo.assigned_to else None,
    )


def _mwo_response(mwo: MaintenanceWorkOrder) -> MwoResponse:
    asset = mwo.asset
    parts = []
    for line in mwo.parts or []:
        product = line.product
        parts.append(
            MwoPartLine(
                id=line.id,
                product_id=line.product_id,
                product_name=product.name if product else f"Product #{line.product_id}",
                quantity=_float(line.quantity),
                unit=product.unit if product else None,
                issued_at=line.issued_at,
                issued_by_name=line.issued_by.name if line.issued_by else None,
            )
        )
    return MwoResponse(
        id=mwo.id,
        work_order_number=mwo.work_order_number,
        asset_id=mwo.asset_id,
        asset_code=asset.asset_code if asset else None,
        asset_name=asset.name if asset else None,
        type=mwo.type,
        priority=mwo.priority,
        status=mwo.status,
        title=mwo.title,
        description=mwo.description,
        reported_at=mwo.reported_at,
        started_at=mwo.started_at,
        completed_at=mwo.completed_at,
        downtime_minutes=mwo.downtime_minutes,
        root_cause=mwo.root_cause,
        resolution_notes=mwo.resolution_notes,
        assigned_to_id=mwo.assigned_to_id,
        assigned_to_name=mwo.assigned_to.name if mwo.assigned_to else None,
        vendor_contact_id=mwo.vendor_contact_id,
        vendor_name=mwo.vendor_contact.name if mwo.vendor_contact else None,
        parts=parts,
    )


def _get_mwo(db: Session, company_id: int, mwo_id: int) -> MaintenanceWorkOrder:
    mwo = (
        db.query(MaintenanceWorkOrder)
        .options(
            joinedload(MaintenanceWorkOrder.asset),
            joinedload(MaintenanceWorkOrder.assigned_to),
            joinedload(MaintenanceWorkOrder.vendor_contact),
            joinedload(MaintenanceWorkOrder.parts).joinedload(MaintenanceWoPart.product),
            joinedload(MaintenanceWorkOrder.parts).joinedload(MaintenanceWoPart.issued_by),
        )
        .filter(MaintenanceWorkOrder.id == mwo_id, MaintenanceWorkOrder.company_id == company_id)
        .first()
    )
    if not mwo:
        raise HTTPException(status_code=404, detail="Maintenance work order not found")
    return mwo


def _get_asset(db: Session, company_id: int, asset_id: int) -> MaintenanceAsset:
    asset = (
        db.query(MaintenanceAsset)
        .options(joinedload(MaintenanceAsset.category), joinedload(MaintenanceAsset.vendor_contact))
        .filter(MaintenanceAsset.id == asset_id, MaintenanceAsset.company_id == company_id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def _has_open_preventive_mwo(db: Session, asset_id: int) -> bool:
    return (
        db.query(MaintenanceWorkOrder.id)
        .filter(
            MaintenanceWorkOrder.asset_id == asset_id,
            MaintenanceWorkOrder.type == "preventive",
            MaintenanceWorkOrder.status.in_(OPEN_MWO_STATUSES),
        )
        .first()
        is not None
    )


def _has_open_breakdown_mwo(db: Session, asset_id: int, exclude_id: int | None = None) -> bool:
    q = db.query(MaintenanceWorkOrder.id).filter(
        MaintenanceWorkOrder.asset_id == asset_id,
        MaintenanceWorkOrder.type == "breakdown",
        MaintenanceWorkOrder.status.in_(OPEN_BREAKDOWN_STATUSES),
    )
    if exclude_id:
        q = q.filter(MaintenanceWorkOrder.id != exclude_id)
    return q.first() is not None


def _notify_critical_breakdown(db: Session, company: Company, settings: MaintenanceSettings, mwo: MaintenanceWorkOrder, asset: MaintenanceAsset) -> None:
    if asset.criticality != "critical" or mwo.type != "breakdown":
        return
    roles = settings.notify_roles_json or DEFAULT_NOTIFY_ROLES
    for role in roles:
        notify_role(
            db,
            company_id=company.id,
            role=role,
            category="maintenance",
            title=f"Critical breakdown: {asset.name}",
            message=f"{mwo.work_order_number} — {mwo.title}",
            link_path=f"/maintenance/work-orders/{mwo.id}",
        )


def _sync_pm_overdue_notifications(db: Session, company: Company, settings: MaintenanceSettings) -> None:
    if not settings.is_enabled:
        return
    today = _utcnow().date()
    overdue_assets = (
        db.query(MaintenanceAsset)
        .filter(
            MaintenanceAsset.company_id == company.id,
            MaintenanceAsset.status != "retired",
            MaintenanceAsset.next_pm_due_date.isnot(None),
            MaintenanceAsset.next_pm_due_date < today,
        )
        .all()
    )
    roles = settings.notify_roles_json or DEFAULT_NOTIFY_ROLES
    for asset in overdue_assets:
        if _has_open_preventive_mwo(db, asset.id):
            continue
        link = f"/maintenance/assets/{asset.id}"
        title = f"PM overdue: {asset.asset_code}"
        already = (
            db.query(Notification.id)
            .filter(
                Notification.company_id == company.id,
                Notification.category == "maintenance",
                Notification.title == title,
                Notification.link_path == link,
                Notification.created_at >= datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
            )
            .first()
        )
        if already:
            continue
        for role in roles:
            notify_role(
                db,
                company_id=company.id,
                role=role,
                category="maintenance",
                title=title,
                message=f"{asset.name} — due {asset.next_pm_due_date}",
                link_path=link,
            )


def _issue_spare_part_stock(
    db: Session,
    product: Product,
    user: User,
    qty: float,
    mwo_number: str,
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
        notes=f"Spare parts for {mwo_number}",
        reference_number=mwo_number,
        reference_type="maintenance_work_order",
        source_module="maintenance",
        allow_negative=allow_negative,
    )
    return movement.id


@router.get("/settings", response_model=MaintenanceSettingsResponse)
def get_settings_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    return _settings_response(_get_settings(db, company))


@router.put("/settings", response_model=MaintenanceSettingsResponse)
def update_settings(
    body: MaintenanceSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.manage_settings")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    log_activity(db, "maintenance_settings_updated", user_id=user.id, details={"company_id": company.id}, ip_address=get_client_ip(request))
    return _settings_response(settings)


@router.get("/categories", response_model=list[AssetCategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    rows = (
        db.query(MaintenanceAssetCategory)
        .filter(MaintenanceAssetCategory.company_id == company.id)
        .order_by(MaintenanceAssetCategory.sort_order, MaintenanceAssetCategory.name)
        .all()
    )
    return [AssetCategoryResponse(id=r.id, name=r.name, sort_order=r.sort_order) for r in rows]


@router.post("/categories", response_model=AssetCategoryResponse)
def create_category(
    body: AssetCategoryCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.manage_settings")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    row = MaintenanceAssetCategory(company_id=company.id, name=body.name.strip(), sort_order=body.sort_order)
    db.add(row)
    db.commit()
    db.refresh(row)
    log_activity(db, "maintenance_category_created", user_id=user.id, details={"category_id": row.id}, ip_address=get_client_ip(request))
    return AssetCategoryResponse(id=row.id, name=row.name, sort_order=row.sort_order)


@router.put("/categories/{category_id}", response_model=AssetCategoryResponse)
def update_category(
    category_id: int,
    body: AssetCategoryUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.manage_settings")),
):
    company = _get_company(db)
    row = (
        db.query(MaintenanceAssetCategory)
        .filter(MaintenanceAssetCategory.id == category_id, MaintenanceAssetCategory.company_id == company.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Category not found")
    if body.name is not None:
        row.name = body.name.strip()
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    db.commit()
    db.refresh(row)
    return AssetCategoryResponse(id=row.id, name=row.name, sort_order=row.sort_order)


@router.get("/dashboard", response_model=MaintenanceDashboardResponse)
def maintenance_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    _sync_pm_overdue_notifications(db, company, settings)

    today = _utcnow().date()
    since_7d = _utcnow() - timedelta(days=7)
    since_30d = _utcnow() - timedelta(days=30)

    operational = (
        db.query(func.count(MaintenanceAsset.id))
        .filter(MaintenanceAsset.company_id == company.id, MaintenanceAsset.status == "operational")
        .scalar()
    )
    breakdown = (
        db.query(func.count(MaintenanceAsset.id))
        .filter(MaintenanceAsset.company_id == company.id, MaintenanceAsset.status == "breakdown")
        .scalar()
    )
    under_maint = (
        db.query(func.count(MaintenanceAsset.id))
        .filter(MaintenanceAsset.company_id == company.id, MaintenanceAsset.status == "under_maintenance")
        .scalar()
    )
    open_wos = (
        db.query(func.count(MaintenanceWorkOrder.id))
        .filter(MaintenanceWorkOrder.company_id == company.id, MaintenanceWorkOrder.status.in_(OPEN_MWO_STATUSES))
        .scalar()
    )
    overdue_pm_count = (
        db.query(func.count(MaintenanceAsset.id))
        .filter(
            MaintenanceAsset.company_id == company.id,
            MaintenanceAsset.status != "retired",
            MaintenanceAsset.next_pm_due_date.isnot(None),
            MaintenanceAsset.next_pm_due_date < today,
        )
        .scalar()
    )
    downtime_7d = (
        db.query(func.coalesce(func.sum(MaintenanceWorkOrder.downtime_minutes), 0))
        .filter(
            MaintenanceWorkOrder.company_id == company.id,
            MaintenanceWorkOrder.status == "completed",
            MaintenanceWorkOrder.completed_at >= since_7d,
        )
        .scalar()
    )
    downtime_30d = (
        db.query(func.coalesce(func.sum(MaintenanceWorkOrder.downtime_minutes), 0))
        .filter(
            MaintenanceWorkOrder.company_id == company.id,
            MaintenanceWorkOrder.status == "completed",
            MaintenanceWorkOrder.completed_at >= since_30d,
        )
        .scalar()
    )

    overdue_assets = (
        db.query(MaintenanceAsset)
        .options(joinedload(MaintenanceAsset.category))
        .filter(
            MaintenanceAsset.company_id == company.id,
            MaintenanceAsset.status != "retired",
            MaintenanceAsset.next_pm_due_date.isnot(None),
            MaintenanceAsset.next_pm_due_date < today,
        )
        .order_by(MaintenanceAsset.next_pm_due_date)
        .limit(10)
        .all()
    )
    open_breakdowns = (
        db.query(MaintenanceWorkOrder)
        .options(joinedload(MaintenanceWorkOrder.asset), joinedload(MaintenanceWorkOrder.assigned_to))
        .filter(
            MaintenanceWorkOrder.company_id == company.id,
            MaintenanceWorkOrder.type == "breakdown",
            MaintenanceWorkOrder.status.in_(OPEN_BREAKDOWN_STATUSES),
        )
        .order_by(MaintenanceWorkOrder.priority.desc(), MaintenanceWorkOrder.reported_at)
        .limit(10)
        .all()
    )
    recent = (
        db.query(MaintenanceWorkOrder)
        .options(joinedload(MaintenanceWorkOrder.asset), joinedload(MaintenanceWorkOrder.assigned_to))
        .filter(MaintenanceWorkOrder.company_id == company.id, MaintenanceWorkOrder.status == "completed")
        .order_by(MaintenanceWorkOrder.completed_at.desc())
        .limit(10)
        .all()
    )

    db.commit()

    return MaintenanceDashboardResponse(
        operational_assets=int(operational or 0),
        breakdown_assets=int(breakdown or 0),
        under_maintenance_assets=int(under_maint or 0),
        open_work_orders=int(open_wos or 0),
        overdue_pm_count=int(overdue_pm_count or 0),
        downtime_hours_7d=round(_float(downtime_7d) / 60, 1),
        downtime_hours_30d=round(_float(downtime_30d) / 60, 1),
        overdue_pm=[_asset_list_item(a, today) for a in overdue_assets],
        open_breakdowns=[_mwo_list_item(m) for m in open_breakdowns],
        recent_completions=[_mwo_list_item(m) for m in recent],
    )


@router.get("/assets", response_model=AssetListResponse)
def list_assets(
    status: str | None = None,
    category_id: int | None = None,
    criticality: str | None = None,
    pm_overdue: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    today = _utcnow().date()
    q = (
        db.query(MaintenanceAsset)
        .options(joinedload(MaintenanceAsset.category))
        .filter(MaintenanceAsset.company_id == company.id)
    )
    if status:
        q = q.filter(MaintenanceAsset.status == status)
    if category_id:
        q = q.filter(MaintenanceAsset.category_id == category_id)
    if criticality:
        q = q.filter(MaintenanceAsset.criticality == criticality)
    if pm_overdue:
        q = q.filter(
            MaintenanceAsset.next_pm_due_date.isnot(None),
            MaintenanceAsset.next_pm_due_date < today,
            MaintenanceAsset.status != "retired",
        )
    rows = q.order_by(MaintenanceAsset.asset_code).all()
    items = [_asset_list_item(a, today) for a in rows]
    return AssetListResponse(items=items, total=len(items))


@router.post("/assets", response_model=AssetResponse)
def create_asset(
    body: AssetCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.manage_assets")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    if body.status not in ASSET_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid asset status")
    if body.criticality not in ASSET_CRITICALITIES:
        raise HTTPException(status_code=400, detail="Invalid criticality")

    prefix = settings.asset_code_prefix or DEFAULT_ASSET_CODE_PREFIX
    asset_code = (body.asset_code or "").strip() or _generate_asset_code(db, company.id, prefix)
    exists = (
        db.query(MaintenanceAsset.id)
        .filter(MaintenanceAsset.company_id == company.id, MaintenanceAsset.asset_code == asset_code)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Asset code already exists")

    interval = body.pm_interval_days if body.pm_interval_days is not None else settings.default_pm_interval_days
    asset = MaintenanceAsset(
        company_id=company.id,
        asset_code=asset_code,
        name=body.name.strip(),
        category_id=body.category_id,
        status=body.status,
        criticality=body.criticality,
        location_notes=body.location_notes,
        manufacturer=body.manufacturer,
        model=body.model,
        serial_number=body.serial_number,
        purchase_date=body.purchase_date,
        warranty_end=body.warranty_end,
        vendor_contact_id=body.vendor_contact_id,
        pm_interval_days=interval,
        notes=body.notes,
        created_by_id=user.id,
    )
    _recalc_next_pm(asset, settings)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    log_activity(db, "maintenance_asset_created", user_id=user.id, details={"asset_id": asset.id, "asset_code": asset_code}, ip_address=get_client_ip(request))
    return _asset_detail_response(asset)


def _asset_detail_response(asset: MaintenanceAsset) -> AssetResponse:
    return AssetResponse(
        id=asset.id,
        asset_code=asset.asset_code,
        name=asset.name,
        category_id=asset.category_id,
        category_name=asset.category.name if asset.category else None,
        status=asset.status,
        criticality=asset.criticality,
        location_notes=asset.location_notes,
        manufacturer=asset.manufacturer,
        model=asset.model,
        serial_number=asset.serial_number,
        purchase_date=asset.purchase_date,
        warranty_end=asset.warranty_end,
        vendor_contact_id=asset.vendor_contact_id,
        vendor_name=asset.vendor_contact.name if asset.vendor_contact else None,
        pm_interval_days=asset.pm_interval_days,
        last_service_date=asset.last_service_date,
        next_pm_due_date=asset.next_pm_due_date,
        notes=asset.notes,
        created_at=asset.created_at,
    )


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    asset = _get_asset(db, company.id, asset_id)
    return _asset_detail_response(asset)


@router.put("/assets/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: int,
    body: AssetUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.manage_assets")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    asset = _get_asset(db, company.id, asset_id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in ASSET_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid asset status")
    if "criticality" in data and data["criticality"] not in ASSET_CRITICALITIES:
        raise HTTPException(status_code=400, detail="Invalid criticality")
    pm_changed = "pm_interval_days" in data
    for key, value in data.items():
        setattr(asset, key, value)
    if pm_changed:
        _recalc_next_pm(asset, settings)
    db.commit()
    db.refresh(asset)
    log_activity(db, "maintenance_asset_updated", user_id=user.id, details={"asset_id": asset.id}, ip_address=get_client_ip(request))
    return _asset_detail_response(asset)


@router.get("/assets/{asset_id}/history", response_model=AssetHistoryResponse)
def asset_history(
    asset_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    _get_asset(db, company.id, asset_id)
    wos = (
        db.query(MaintenanceWorkOrder)
        .options(
            joinedload(MaintenanceWorkOrder.parts).joinedload(MaintenanceWoPart.product),
        )
        .filter(
            MaintenanceWorkOrder.company_id == company.id,
            MaintenanceWorkOrder.asset_id == asset_id,
            MaintenanceWorkOrder.status == "completed",
        )
        .order_by(MaintenanceWorkOrder.completed_at.desc())
        .all()
    )
    items = []
    for mwo in wos:
        parts = [
            {
                "product_id": p.product_id,
                "product_name": p.product.name if p.product else None,
                "quantity": _float(p.quantity),
            }
            for p in mwo.parts or []
        ]
        items.append(
            AssetHistoryItem(
                work_order_id=mwo.id,
                work_order_number=mwo.work_order_number,
                type=mwo.type,
                status=mwo.status,
                completed_at=mwo.completed_at,
                downtime_minutes=mwo.downtime_minutes,
                resolution_notes=mwo.resolution_notes,
                root_cause=mwo.root_cause,
                parts=parts,
            )
        )
    return AssetHistoryResponse(items=items)


@router.get("/work-orders", response_model=MwoListResponse)
def list_work_orders(
    type: str | None = None,
    status: str | None = None,
    asset_id: int | None = None,
    assigned_to_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    q = (
        db.query(MaintenanceWorkOrder)
        .options(joinedload(MaintenanceWorkOrder.asset), joinedload(MaintenanceWorkOrder.assigned_to))
        .filter(MaintenanceWorkOrder.company_id == company.id)
    )
    if type:
        q = q.filter(MaintenanceWorkOrder.type == type)
    if status:
        q = q.filter(MaintenanceWorkOrder.status == status)
    if asset_id:
        q = q.filter(MaintenanceWorkOrder.asset_id == asset_id)
    if assigned_to_id:
        q = q.filter(MaintenanceWorkOrder.assigned_to_id == assigned_to_id)
    rows = q.order_by(MaintenanceWorkOrder.reported_at.desc()).all()
    return MwoListResponse(items=[_mwo_list_item(m) for m in rows], total=len(rows))


@router.post("/work-orders", response_model=MwoResponse)
def create_work_order(
    body: MwoCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.create_wo")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    if body.type not in MWO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid work order type")
    if body.priority not in MWO_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority")
    if body.status not in ("draft", "open"):
        raise HTTPException(status_code=400, detail="New work orders must be draft or open")

    asset = _get_asset(db, company.id, body.asset_id)
    if asset.status == "retired":
        raise HTTPException(status_code=400, detail="Cannot create work order for retired asset")

    prefix = settings.work_order_prefix or DEFAULT_WORK_ORDER_PREFIX
    mwo = MaintenanceWorkOrder(
        company_id=company.id,
        work_order_number=_generate_mwo_number(db, company.id, prefix),
        asset_id=asset.id,
        type=body.type,
        priority=body.priority,
        status=body.status,
        title=body.title.strip(),
        description=body.description,
        reported_at=_utcnow(),
        assigned_to_id=body.assigned_to_id,
        vendor_contact_id=body.vendor_contact_id,
        created_by_id=user.id,
    )
    if body.type == "breakdown":
        asset.status = "breakdown"
    elif body.status in ("open", "in_progress"):
        asset.status = "under_maintenance"
    db.add(mwo)
    db.flush()
    _notify_critical_breakdown(db, company, settings, mwo, asset)
    db.commit()
    mwo = _get_mwo(db, company.id, mwo.id)
    log_activity(
        db,
        "maintenance_wo_created",
        user_id=user.id,
        details={"work_order_id": mwo.id, "work_order_number": mwo.work_order_number, "type": mwo.type},
        ip_address=get_client_ip(request),
    )
    return _mwo_response(mwo)


@router.get("/work-orders/{mwo_id}", response_model=MwoResponse)
def get_work_order(
    mwo_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    return _mwo_response(_get_mwo(db, company.id, mwo_id))


@router.put("/work-orders/{mwo_id}/status", response_model=MwoResponse)
def update_work_order_status(
    mwo_id: int,
    body: MwoStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.execute_wo")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    mwo = _get_mwo(db, company.id, mwo_id)
    new_status = body.status
    if new_status not in MWO_STATUS_TRANSITIONS:
        raise HTTPException(status_code=400, detail="Invalid status")
    allowed = MWO_STATUS_TRANSITIONS.get(mwo.status, set())
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {mwo.status} to {new_status}")
    if new_status == "cancelled":
        raise HTTPException(status_code=400, detail="Use cancel endpoint to cancel work orders")

    asset = mwo.asset
    old_status = mwo.status
    mwo.status = new_status
    if new_status == "in_progress" and not mwo.started_at:
        mwo.started_at = _utcnow()
    if new_status == "in_progress":
        if asset and asset.status not in ("breakdown", "retired"):
            asset.status = "under_maintenance"
    if new_status == "cancelled":
        if mwo.type == "breakdown" and asset and not _has_open_breakdown_mwo(db, asset.id, exclude_id=mwo.id):
            asset.status = "operational"
        elif asset and asset.status == "under_maintenance":
            asset.status = "operational"

    db.commit()
    mwo = _get_mwo(db, company.id, mwo_id)
    log_activity(
        db,
        "maintenance_wo_status_changed",
        user_id=user.id,
        details={"work_order_id": mwo.id, "from": old_status, "to": new_status},
        ip_address=get_client_ip(request),
    )
    return _mwo_response(mwo)


@router.put("/work-orders/{mwo_id}/cancel", response_model=MwoResponse)
def cancel_work_order(
    mwo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.cancel_wo")),
):
    return update_work_order_status(mwo_id, MwoStatusUpdateRequest(status="cancelled"), request, db, user)


@router.post("/work-orders/{mwo_id}/parts", response_model=MwoResponse)
def issue_parts(
    mwo_id: int,
    body: MwoIssuePartsRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.issue_parts")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    mwo = _get_mwo(db, company.id, mwo_id)
    if mwo.status not in ("in_progress", "waiting_parts", "open"):
        raise HTTPException(status_code=400, detail="Parts can only be issued to active work orders")

    product = db.query(Product).filter(Product.id == body.product_id, Product.company_id == company.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_spare_part and not product.inventory_tracked:
        raise HTTPException(status_code=400, detail="Product is not flagged as spare part or inventory-tracked")

    qty = _float(body.quantity)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    movement_id = None
    if settings.auto_deduct_spare_parts and product.inventory_tracked:
        on_hand = _float(product.on_hand_quantity)
        if on_hand < qty and not settings.allow_negative_spare_parts:
            raise HTTPException(status_code=400, detail="Insufficient stock for this spare part")
        movement_id = _issue_spare_part_stock(
            db,
            product,
            user,
            qty,
            mwo.work_order_number,
            allow_negative=bool(settings.allow_negative_spare_parts),
        )

    part = MaintenanceWoPart(
        work_order_id=mwo.id,
        product_id=product.id,
        quantity=qty,
        stock_movement_id=movement_id,
        issued_by_id=user.id,
        issued_at=_utcnow(),
    )
    db.add(part)
    db.commit()
    mwo = _get_mwo(db, company.id, mwo_id)
    log_activity(
        db,
        "maintenance_wo_parts_issued",
        user_id=user.id,
        details={"work_order_id": mwo.id, "product_id": product.id, "quantity": qty},
        ip_address=get_client_ip(request),
    )
    return _mwo_response(mwo)


@router.post("/work-orders/{mwo_id}/complete", response_model=MwoResponse)
def complete_work_order(
    mwo_id: int,
    body: MwoCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.execute_wo")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    mwo = _get_mwo(db, company.id, mwo_id)
    if mwo.status not in ("in_progress", "waiting_parts", "open"):
        raise HTTPException(status_code=400, detail="Work order cannot be completed from current status")
    if mwo.type == "breakdown" and not body.resolution_notes.strip():
        raise HTTPException(status_code=400, detail="Resolution notes required for breakdown work orders")

    asset = mwo.asset
    now = _utcnow()
    mwo.status = "completed"
    mwo.completed_at = now
    mwo.resolution_notes = body.resolution_notes.strip()
    mwo.root_cause = body.root_cause
    if body.downtime_minutes is not None:
        if body.downtime_minutes < 0:
            raise HTTPException(status_code=400, detail="Downtime must be non-negative")
        mwo.downtime_minutes = body.downtime_minutes
    elif mwo.reported_at:
        mwo.downtime_minutes = max(0, int((now - mwo.reported_at).total_seconds() // 60))

    if mwo.type == "preventive" and asset:
        asset.last_service_date = now.date()
        _recalc_next_pm(asset, settings)
    if mwo.type == "breakdown" and asset:
        if not _has_open_breakdown_mwo(db, asset.id, exclude_id=mwo.id):
            asset.status = "operational"
    elif asset and asset.status == "under_maintenance":
        asset.status = "operational"

    db.commit()
    mwo = _get_mwo(db, company.id, mwo_id)
    log_activity(
        db,
        "maintenance_wo_completed",
        user_id=user.id,
        details={"work_order_id": mwo.id, "type": mwo.type},
        ip_address=get_client_ip(request),
    )
    if mwo.type == "breakdown":
        log_activity(db, "mwo_breakdown_closed", user_id=user.id, details={"work_order_id": mwo.id}, ip_address=get_client_ip(request))
    return _mwo_response(mwo)


@router.get("/pm-schedule", response_model=PmScheduleResponse)
def pm_schedule(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("maintenance.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    today = _utcnow().date()
    assets = (
        db.query(MaintenanceAsset)
        .options(joinedload(MaintenanceAsset.category))
        .filter(
            MaintenanceAsset.company_id == company.id,
            MaintenanceAsset.status != "retired",
            MaintenanceAsset.next_pm_due_date.isnot(None),
        )
        .order_by(MaintenanceAsset.next_pm_due_date)
        .all()
    )
    items = []
    for asset in assets:
        days_overdue = (today - asset.next_pm_due_date).days if asset.next_pm_due_date and asset.next_pm_due_date < today else 0
        items.append(
            PmScheduleItem(
                asset_id=asset.id,
                asset_code=asset.asset_code,
                asset_name=asset.name,
                category_name=asset.category.name if asset.category else None,
                next_pm_due_date=asset.next_pm_due_date,
                last_service_date=asset.last_service_date,
                pm_interval_days=asset.pm_interval_days or settings.default_pm_interval_days,
                days_overdue=max(0, days_overdue),
                has_open_preventive_mwo=_has_open_preventive_mwo(db, asset.id),
            )
        )
    return PmScheduleResponse(items=items)


@router.post("/pm-schedule/generate", response_model=PmGenerateResponse)
def generate_pm_work_orders(
    body: PmGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance.create_wo")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    if not body.asset_ids:
        raise HTTPException(status_code=400, detail="Select at least one asset")

    prefix = settings.work_order_prefix or DEFAULT_WORK_ORDER_PREFIX
    created: list[MaintenanceWorkOrder] = []
    today = _utcnow().date()

    for asset_id in body.asset_ids:
        asset = _get_asset(db, company.id, asset_id)
        if asset.status == "retired":
            continue
        if asset.next_pm_due_date and asset.next_pm_due_date > today:
            continue
        if _has_open_preventive_mwo(db, asset.id):
            continue
        mwo = MaintenanceWorkOrder(
            company_id=company.id,
            work_order_number=_generate_mwo_number(db, company.id, prefix),
            asset_id=asset.id,
            type="preventive",
            priority="normal",
            status="open",
            title=f"Preventive maintenance — {asset.name}",
            description="Scheduled PM",
            reported_at=_utcnow(),
            created_by_id=user.id,
        )
        asset.status = "under_maintenance"
        db.add(mwo)
        created.append(mwo)

    db.commit()
    items = []
    for mwo in created:
        db.refresh(mwo)
        mwo = _get_mwo(db, company.id, mwo.id)
        items.append(_mwo_list_item(mwo))
        log_activity(
            db,
            "maintenance_pm_wo_generated",
            user_id=user.id,
            details={"work_order_id": mwo.id, "asset_id": mwo.asset_id},
            ip_address=get_client_ip(request),
        )
    return PmGenerateResponse(created=items)


def seed_asset_categories(db: Session, company_id: int) -> None:
    for row in SEED_ASSET_CATEGORIES:
        exists = (
            db.query(MaintenanceAssetCategory.id)
            .filter(MaintenanceAssetCategory.company_id == company_id, MaintenanceAssetCategory.name == row["name"])
            .first()
        )
        if not exists:
            db.add(MaintenanceAssetCategory(company_id=company_id, **row))
