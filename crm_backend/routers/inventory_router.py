from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from inventory_config import (
    ADJUSTMENT_REASON_LABELS,
    ADJUSTMENT_REASONS,
    DAMAGE_REASON_LABELS,
    DAMAGE_REASONS,
    DIRECTION_IN,
    DIRECTION_OUT,
    INVENTORY_STATUS_LABELS,
    MOVEMENT_DIRECTIONS,
    MOVEMENT_TYPE_LABELS,
    MOVEMENT_TYPES,
    OUT_MOVEMENT_TYPES,
)
from models import Company, Product, StockMovement, User
from permissions import role_has_permission
from schemas import (
    InventoryEnableTrackingRequest,
    InventoryListResponse,
    InventoryMovementTypeOption,
    InventoryOpeningStockRequest,
    InventoryProductResponse,
    InventoryReasonOption,
    InventoryRecordMovementRequest,
    InventorySettingsUpdateRequest,
    InventoryStatsResponse,
    InventoryStatusOption,
    StockMovementListResponse,
    StockMovementResponse,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _get_company(db: Session, user: User) -> Company:
    return get_current_company(db, user)


def _float(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _stock_value(product: Product) -> float:
    return _float(product.on_hand_quantity) * _float(product.unit_valuation)


def _inventory_status(product: Product) -> str:
    if not product.inventory_tracked:
        return "not_tracked"
    if product.status != "active":
        return "inactive"
    if not product.opening_recorded:
        return "awaiting_opening"
    qty = _float(product.on_hand_quantity)
    if qty <= 0:
        return "out_of_stock"
    if product.reorder_level is not None and qty <= _float(product.reorder_level):
        return "low_stock"
    return "active"


def _movement_response(m: StockMovement) -> StockMovementResponse:
    return StockMovementResponse(
        id=m.id,
        product_id=m.product_id,
        product_name=m.product.name if m.product else None,
        product_sku=m.product.service_code if m.product else None,
        movement_type=m.movement_type,
        direction=m.direction,
        quantity=_float(m.quantity),
        unit_value=_float(m.unit_value),
        total_value=_float(m.total_value),
        quantity_before=_float(m.quantity_before),
        quantity_after=_float(m.quantity_after),
        movement_date=m.movement_date,
        reference_type=m.reference_type,
        reference_id=m.reference_id,
        reference_number=m.reference_number,
        source_module=m.source_module,
        reason=m.reason,
        notes=m.notes,
        negative_override=m.negative_override,
        recorded_by_name=m.recorded_by.name if m.recorded_by else None,
        created_at=m.created_at,
    )


def _movement_totals(movements: list[StockMovement]) -> dict[str, float]:
    purchased = sold = damaged = adj_in = adj_out = 0.0
    for m in movements:
        qty = _float(m.quantity)
        if m.movement_type == "purchase":
            purchased += qty
        elif m.movement_type == "sale":
            sold += qty
        elif m.movement_type == "damage":
            damaged += qty
        elif m.movement_type == "adjustment":
            if m.direction == DIRECTION_IN:
                adj_in += qty
            else:
                adj_out += qty
    return {
        "total_purchased": purchased,
        "total_sold": sold,
        "total_damaged": damaged,
        "net_adjustments": adj_in - adj_out,
    }


def _product_response(product: Product, movements: list[StockMovement] | None = None) -> InventoryProductResponse:
    mvts = movements if movements is not None else list(product.stock_movements or [])
    totals = _movement_totals(mvts)
    return InventoryProductResponse(
        id=product.id,
        service_code=product.service_code,
        name=product.name,
        category=product.category,
        unit=product.unit,
        status=product.status,
        inventory_tracked=product.inventory_tracked,
        on_hand_quantity=_float(product.on_hand_quantity),
        unit_valuation=_float(product.unit_valuation),
        stock_value=_stock_value(product),
        reorder_level=_float(product.reorder_level) if product.reorder_level is not None else None,
        opening_recorded=product.opening_recorded,
        inventory_status=_inventory_status(product),
        last_movement_at=product.last_movement_at,
        total_purchased=totals["total_purchased"],
        total_sold=totals["total_sold"],
        total_damaged=totals["total_damaged"],
        net_adjustments=totals["net_adjustments"],
        movements=[_movement_response(m) for m in mvts[:50]],
    )


def _get_product(db: Session, product_id: int, company_id: int) -> Product:
    product = (
        db.query(Product)
        .options(joinedload(Product.stock_movements).joinedload(StockMovement.recorded_by))
        .filter(Product.id == product_id, Product.company_id == company_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _validate_movement_type(movement_type: str) -> None:
    if movement_type not in MOVEMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Movement type must be one of: {', '.join(MOVEMENT_TYPES)}")


def _apply_movement(
    db: Session,
    product: Product,
    user: User,
    movement_type: str,
    quantity: float,
    unit_value: float,
    movement_date: datetime,
    *,
    adjustment_direction: str | None = None,
    reason: str | None = None,
    notes: str | None = None,
    reference_number: str | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    source_module: str = "manual",
    allow_negative: bool = False,
) -> StockMovement:
    _validate_movement_type(movement_type)
    if not product.inventory_tracked:
        raise HTTPException(status_code=400, detail="Product is not inventory-tracked")
    if product.status != "active":
        raise HTTPException(status_code=400, detail="Cannot move stock on inactive product")

    if movement_type == "opening":
        if product.opening_recorded:
            raise HTTPException(status_code=400, detail="Opening stock already recorded for this product")
    elif not product.opening_recorded:
        raise HTTPException(status_code=400, detail="Record opening stock before other movements")

    if movement_type in {"damage", "adjustment"} and not reason:
        raise HTTPException(status_code=400, detail="Reason is required for damage and adjustment movements")

    if movement_type == "adjustment":
        if adjustment_direction not in {DIRECTION_IN, DIRECTION_OUT}:
            raise HTTPException(status_code=400, detail="Adjustment direction must be in or out")
        direction = adjustment_direction
    else:
        direction = MOVEMENT_DIRECTIONS[movement_type]

    qty_before = _float(product.on_hand_quantity)
    delta = quantity if direction == DIRECTION_IN else -quantity
    qty_after = qty_before + delta

    if qty_after < 0 and not allow_negative:
        raise HTTPException(status_code=400, detail="Insufficient stock for this movement")

    movement = StockMovement(
        company_id=product.company_id,
        product_id=product.id,
        recorded_by_id=user.id,
        movement_type=movement_type,
        direction=direction,
        quantity=quantity,
        unit_value=unit_value,
        total_value=quantity * unit_value,
        quantity_before=qty_before,
        quantity_after=qty_after,
        movement_date=movement_date,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_number=reference_number,
        source_module=source_module,
        reason=reason,
        notes=notes,
        negative_override=allow_negative and qty_after < 0,
    )
    db.add(movement)

    product.on_hand_quantity = qty_after
    product.unit_valuation = unit_value
    product.last_movement_at = movement_date
    if movement_type == "opening":
        product.opening_recorded = True

    return movement


@router.get("/movement-types", response_model=list[InventoryMovementTypeOption])
def movement_types(_: User = Depends(require_permission("inventory.view"))):
    return [InventoryMovementTypeOption(value=t, label=MOVEMENT_TYPE_LABELS[t]) for t in MOVEMENT_TYPES if t != "opening"]


@router.get("/statuses", response_model=list[InventoryStatusOption])
def statuses(_: User = Depends(require_permission("inventory.view"))):
    return [InventoryStatusOption(value=s, label=INVENTORY_STATUS_LABELS[s]) for s in INVENTORY_STATUS_LABELS]


@router.get("/damage-reasons", response_model=list[InventoryReasonOption])
def damage_reasons(_: User = Depends(require_permission("inventory.view"))):
    return [InventoryReasonOption(value=r, label=DAMAGE_REASON_LABELS[r]) for r in DAMAGE_REASONS]


@router.get("/adjustment-reasons", response_model=list[InventoryReasonOption])
def adjustment_reasons(_: User = Depends(require_permission("inventory.view"))):
    return [InventoryReasonOption(value=r, label=ADJUSTMENT_REASON_LABELS[r]) for r in ADJUSTMENT_REASONS]


@router.get("/stats/summary", response_model=InventoryStatsResponse)
def stats(user: User = Depends(require_permission("inventory.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    products = db.query(Product).filter(Product.company_id == company.id, Product.inventory_tracked.is_(True)).all()
    tracked = [p for p in products if p.status == "active"]
    total_value = sum(_stock_value(p) for p in tracked)
    low_stock = sum(1 for p in tracked if _inventory_status(p) == "low_stock")
    out_of_stock = sum(1 for p in tracked if _inventory_status(p) == "out_of_stock")

    top = max(tracked, key=_stock_value, default=None)
    cat_totals: dict[str, float] = {}
    for p in tracked:
        cat = p.category or "Uncategorized"
        cat_totals[cat] = cat_totals.get(cat, 0) + _stock_value(p)

    recent = (
        db.query(StockMovement)
        .options(joinedload(StockMovement.product), joinedload(StockMovement.recorded_by))
        .filter(StockMovement.company_id == company.id)
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .limit(10)
        .all()
    )
    movements_month = (
        db.query(func.count(StockMovement.id))
        .filter(StockMovement.company_id == company.id, StockMovement.movement_date >= month_start)
        .scalar()
    )

    return InventoryStatsResponse(
        total_stock_value=total_value,
        tracked_products=len(tracked),
        low_stock_count=low_stock,
        out_of_stock_count=out_of_stock,
        movements_this_month=movements_month or 0,
        top_product_name=top.name if top else None,
        top_product_value=_stock_value(top) if top else 0,
        by_category=[{"name": k, "value": v} for k, v in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)],
        recent_movements=[_movement_response(m) for m in recent],
    )


@router.get("/movements", response_model=StockMovementListResponse)
def list_movements(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    movement_type: str | None = None,
    product_id: int | None = None,
    search: str | None = None,
    user: User = Depends(require_permission("inventory.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(StockMovement)
        .options(joinedload(StockMovement.product), joinedload(StockMovement.recorded_by))
        .filter(StockMovement.company_id == company.id)
    )
    if movement_type:
        _validate_movement_type(movement_type)
        query = query.filter(StockMovement.movement_type == movement_type)
    if product_id:
        query = query.filter(StockMovement.product_id == product_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.join(Product).filter(or_(Product.name.ilike(term), Product.service_code.ilike(term)))
    total = query.count()
    items = query.order_by(StockMovement.movement_date.desc(), StockMovement.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return StockMovementListResponse(items=[_movement_response(m) for m in items], total=total, page=page, limit=limit)


@router.get("/low-stock", response_model=InventoryListResponse)
def low_stock(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("inventory.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    products = (
        db.query(Product)
        .options(joinedload(Product.stock_movements))
        .filter(Product.company_id == company.id, Product.inventory_tracked.is_(True), Product.status == "active")
        .all()
    )
    filtered = [p for p in products if _inventory_status(p) in {"low_stock", "out_of_stock"}]
    filtered.sort(key=lambda p: (_float(p.on_hand_quantity), -_stock_value(p)))
    total = len(filtered)
    page_items = filtered[(page - 1) * limit : page * limit]
    return InventoryListResponse(
        items=[_product_response(p) for p in page_items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("", response_model=InventoryListResponse)
def list_inventory(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    category: str | None = None,
    inventory_status: str | None = None,
    tracked_only: bool = True,
    user: User = Depends(require_permission("inventory.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = db.query(Product).options(joinedload(Product.stock_movements)).filter(Product.company_id == company.id)
    if tracked_only:
        query = query.filter(Product.inventory_tracked.is_(True))
    if category:
        query = query.filter(Product.category == category)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.name.ilike(term), Product.service_code.ilike(term)))
    products = query.order_by(Product.name).all()
    if inventory_status:
        products = [p for p in products if _inventory_status(p) == inventory_status]
    total = len(products)
    page_items = products[(page - 1) * limit : page * limit]
    return InventoryListResponse(
        items=[_product_response(p) for p in page_items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/products/{product_id}", response_model=InventoryProductResponse)
def get_inventory_product(
    product_id: int,
    user: User = Depends(require_permission("inventory.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    product = _get_product(db, product_id, company.id)
    movements = (
        db.query(StockMovement)
        .options(joinedload(StockMovement.recorded_by), joinedload(StockMovement.product))
        .filter(StockMovement.product_id == product.id)
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .all()
    )
    return _product_response(product, movements)


@router.post("/products/{product_id}/enable-tracking", response_model=InventoryProductResponse)
def enable_tracking(
    product_id: int,
    payload: InventoryEnableTrackingRequest,
    request: Request,
    user: User = Depends(require_permission("inventory.enable_tracking")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    product = _get_product(db, product_id, company.id)
    if product.inventory_tracked:
        raise HTTPException(status_code=400, detail="Inventory tracking already enabled")
    product.inventory_tracked = True
    product.reorder_level = payload.reorder_level
    product.unit_valuation = payload.unit_valuation
    db.commit()
    log_activity(db, "inventory_tracking_enabled", user_id=user.id, email=user.email, details=f"Tracking enabled: {product.name}", ip_address=get_client_ip(request))
    return _product_response(_get_product(db, product_id, company.id))


@router.put("/products/{product_id}/settings", response_model=InventoryProductResponse)
def update_settings(
    product_id: int,
    payload: InventorySettingsUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("inventory.manage_settings")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    product = _get_product(db, product_id, company.id)
    if not product.inventory_tracked:
        raise HTTPException(status_code=400, detail="Product is not inventory-tracked")
    if payload.reorder_level is not None:
        product.reorder_level = payload.reorder_level
    if payload.unit_valuation is not None:
        product.unit_valuation = payload.unit_valuation
    db.commit()
    log_activity(db, "inventory_settings_updated", user_id=user.id, email=user.email, details=f"Settings updated: {product.name}", ip_address=get_client_ip(request))
    return _product_response(_get_product(db, product_id, company.id))


@router.post("/products/{product_id}/opening-stock", response_model=InventoryProductResponse)
def record_opening_stock(
    product_id: int,
    payload: InventoryOpeningStockRequest,
    request: Request,
    user: User = Depends(require_permission("inventory.record_opening")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    product = _get_product(db, product_id, company.id)
    _apply_movement(
        db, product, user, "opening", payload.quantity, payload.unit_valuation, payload.movement_date,
        notes=payload.notes, reference_number=payload.reference_number,
    )
    db.commit()
    log_activity(db, "inventory_opening_recorded", user_id=user.id, email=user.email, details=f"Opening stock: {product.name}", ip_address=get_client_ip(request))
    return _product_response(_get_product(db, product_id, company.id))


@router.post("/products/{product_id}/movements", response_model=InventoryProductResponse)
def record_movement(
    product_id: int,
    payload: InventoryRecordMovementRequest,
    request: Request,
    user: User = Depends(require_permission("inventory.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    product = _get_product(db, product_id, company.id)

    perm_map = {
        "purchase": "inventory.record_purchase",
        "sale": "inventory.record_sale",
        "damage": "inventory.record_damage",
        "adjustment": "inventory.adjust",
    }
    required = perm_map.get(payload.movement_type)
    if not required or not role_has_permission(db, user.role, required):
        raise HTTPException(status_code=403, detail="You do not have permission for this movement type")

    allow_negative = False
    if payload.movement_type in OUT_MOVEMENT_TYPES and _float(product.on_hand_quantity) < payload.quantity:
        if role_has_permission(db, user.role, "inventory.override_negative"):
            allow_negative = True
        else:
            raise HTTPException(status_code=400, detail="Insufficient stock for this movement")

    _apply_movement(
        db, product, user, payload.movement_type, payload.quantity, payload.unit_valuation, payload.movement_date,
        adjustment_direction=payload.adjustment_direction,
        reason=payload.reason,
        notes=payload.notes,
        reference_number=payload.reference_number,
        allow_negative=allow_negative,
    )
    db.commit()
    log_activity(db, "inventory_movement_recorded", user_id=user.id, email=user.email, details=f"{payload.movement_type} on {product.name}", ip_address=get_client_ip(request))
    return _product_response(_get_product(db, product_id, company.id))
