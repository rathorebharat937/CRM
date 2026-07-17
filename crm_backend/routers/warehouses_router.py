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
    ADJUSTMENT_REASONS,
    DAMAGE_REASONS,
    DIRECTION_IN,
    DIRECTION_OUT,
    MOVEMENT_DIRECTIONS,
)
from models import (
    Company,
    LocationStock,
    LocationStockMovement,
    Product,
    StockMovement,
    User,
    WarehouseLocation,
)
from permissions import role_has_permission
from schemas import (
    LocationStockListResponse,
    LocationStockMovementListResponse,
    LocationStockMovementResponse,
    LocationStockResponse,
    WarehouseLocationCreateRequest,
    WarehouseLocationDetailResponse,
    WarehouseLocationListResponse,
    WarehouseLocationResponse,
    WarehouseLocationUpdateRequest,
    WarehouseOptionResponse,
    WarehouseRecordMovementRequest,
    WarehouseStatsResponse,
    WarehouseTransferListResponse,
    WarehouseTransferRequest,
    WarehouseTransferResponse,
)
from warehouse_config import (
    DEFAULT_TRANSFER_PREFIX,
    INVENTORY_SYNC_TYPES,
    LOCATION_MOVEMENT_DIRECTIONS,
    LOCATION_MOVEMENT_LABELS,
    LOCATION_MOVEMENT_TYPES,
    LOCATION_STATUS_LABELS,
    LOCATION_STATUSES,
    LOCATION_TYPE_LABELS,
    LOCATION_TYPES,
)

router = APIRouter(prefix="/warehouses", tags=["warehouses"])

MOVEMENT_PERMISSIONS = {
    "receipt": "warehouses.record_receipt",
    "issue": "warehouses.record_issue",
    "damage": "warehouses.record_damage",
    "adjustment": "warehouses.adjust",
}




def _float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _stock_value(qty, unit_val) -> float:
    return _float(qty) * _float(unit_val)


def _location_stock_status(stock: LocationStock) -> str:
    qty = _float(stock.on_hand_quantity)
    if qty <= 0:
        return "out_of_stock"
    reorder = stock.reorder_level
    if reorder is not None and qty <= _float(reorder):
        return "low_stock"
    return "active"


def _ancestors(location: WarehouseLocation, cache: dict[int, WarehouseLocation] | None = None) -> list[WarehouseLocation]:
    chain: list[WarehouseLocation] = []
    current = location
    seen: set[int] = set()
    while current.parent_id:
        if current.parent_id in seen:
            break
        seen.add(current.parent_id)
        parent = current.parent if current.parent else (cache or {}).get(current.parent_id)
        if not parent:
            break
        chain.insert(0, parent)
        current = parent
    return chain


def _branch_name(location: WarehouseLocation, cache: dict[int, WarehouseLocation] | None = None) -> str | None:
    for loc in [location, *_ancestors(location, cache)]:
        if loc.location_type == "branch":
            return loc.name
    return None


def _warehouse_name(location: WarehouseLocation, cache: dict[int, WarehouseLocation] | None = None) -> str | None:
    for loc in [location, *_ancestors(location, cache)]:
        if loc.location_type in {"warehouse", "store"}:
            return loc.name
    return None


def _location_path(location: WarehouseLocation, cache: dict[int, WarehouseLocation] | None = None) -> str:
    parts = [a.name for a in _ancestors(location, cache)] + [location.name]
    return " / ".join(parts)


def _location_cache(db: Session, company_id: int) -> dict[int, WarehouseLocation]:
    locations = db.query(WarehouseLocation).filter(WarehouseLocation.company_id == company_id).all()
    return {loc.id: loc for loc in locations}


def _location_totals(db: Session, location_id: int) -> dict:
    rows = db.query(LocationStock).filter(LocationStock.location_id == location_id).all()
    sku_count = len(rows)
    total_on_hand = sum(_float(r.on_hand_quantity) for r in rows)
    total_value = sum(_stock_value(r.on_hand_quantity, r.unit_valuation) for r in rows)
    low_stock = sum(1 for r in rows if _location_stock_status(r) == "low_stock")
    return {
        "sku_count": sku_count,
        "total_on_hand": total_on_hand,
        "total_stock_value": total_value,
        "low_stock_count": low_stock,
    }


def _location_response(
    location: WarehouseLocation,
    *,
    cache: dict[int, WarehouseLocation] | None = None,
    totals: dict | None = None,
    child_count: int = 0,
) -> WarehouseLocationResponse:
    if cache and location.parent_id and not location.parent:
        location.parent = cache.get(location.parent_id)
    t = totals or {}
    return WarehouseLocationResponse(
        id=location.id,
        location_code=location.location_code,
        name=location.name,
        location_type=location.location_type,
        parent_id=location.parent_id,
        parent_name=location.parent.name if location.parent else None,
        status=location.status,
        address=location.address,
        notes=location.notes,
        is_default_receiving=location.is_default_receiving,
        is_default_dispatch=location.is_default_dispatch,
        branch_name=_branch_name(location, cache),
        warehouse_name=_warehouse_name(location, cache),
        path=_location_path(location, cache),
        sku_count=t.get("sku_count", 0),
        total_on_hand=t.get("total_on_hand", 0),
        total_stock_value=t.get("total_stock_value", 0),
        low_stock_count=t.get("low_stock_count", 0),
        child_count=child_count,
        created_at=location.created_at,
        updated_at=location.updated_at,
    )


def _stock_response(stock: LocationStock, cache: dict[int, WarehouseLocation] | None = None) -> LocationStockResponse:
    loc = stock.location
    if cache and loc and loc.id in cache:
        loc = cache[loc.id]
    return LocationStockResponse(
        id=stock.id,
        product_id=stock.product_id,
        product_name=stock.product.name if stock.product else None,
        product_sku=stock.product.service_code if stock.product else None,
        product_category=stock.product.category if stock.product else None,
        location_id=stock.location_id,
        location_name=loc.name if loc else None,
        location_code=loc.location_code if loc else None,
        location_type=loc.location_type if loc else None,
        branch_name=_branch_name(loc, cache) if loc else None,
        warehouse_name=_warehouse_name(loc, cache) if loc else None,
        location_path=_location_path(loc, cache) if loc else None,
        on_hand_quantity=_float(stock.on_hand_quantity),
        available_quantity=_float(stock.on_hand_quantity),
        unit_valuation=_float(stock.unit_valuation),
        stock_value=_stock_value(stock.on_hand_quantity, stock.unit_valuation),
        reorder_level=_float(stock.reorder_level) if stock.reorder_level is not None else None,
        stock_status=_location_stock_status(stock),
        last_movement_at=stock.last_movement_at,
    )


def _movement_response(m: LocationStockMovement, cache: dict[int, WarehouseLocation] | None = None) -> LocationStockMovementResponse:
    loc = m.location
    return LocationStockMovementResponse(
        id=m.id,
        product_id=m.product_id,
        product_name=m.product.name if m.product else None,
        product_sku=m.product.service_code if m.product else None,
        location_id=m.location_id,
        location_name=loc.name if loc else None,
        location_path=_location_path(loc, cache) if loc else None,
        movement_type=m.movement_type,
        direction=m.direction,
        quantity=_float(m.quantity),
        unit_value=_float(m.unit_value),
        total_value=_float(m.total_value),
        quantity_before=_float(m.quantity_before),
        quantity_after=_float(m.quantity_after),
        movement_date=m.movement_date,
        transfer_reference=m.transfer_reference,
        reference_number=m.reference_number,
        linked_stock_movement_id=m.linked_stock_movement_id,
        reason=m.reason,
        notes=m.notes,
        negative_override=m.negative_override,
        recorded_by_name=m.recorded_by.name if m.recorded_by else None,
        created_at=m.created_at,
    )


def _transfer_response(out_m: LocationStockMovement, in_m: LocationStockMovement, cache: dict) -> WarehouseTransferResponse:
    return WarehouseTransferResponse(
        transfer_reference=out_m.transfer_reference or "",
        transfer_out=_movement_response(out_m, cache),
        transfer_in=_movement_response(in_m, cache),
    )


def _get_location(db: Session, location_id: int, company_id: int) -> WarehouseLocation:
    location = (
        db.query(WarehouseLocation)
        .options(joinedload(WarehouseLocation.parent))
        .filter(WarehouseLocation.id == location_id, WarehouseLocation.company_id == company_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


def _get_product(db: Session, product_id: int, company_id: int) -> Product:
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == company_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _validate_location_type(location_type: str) -> None:
    if location_type not in LOCATION_TYPES:
        raise HTTPException(status_code=400, detail=f"Location type must be one of: {', '.join(LOCATION_TYPES)}")


def _validate_location_status(status: str) -> None:
    if status not in LOCATION_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(LOCATION_STATUSES)}")


def _validate_movement_type(movement_type: str) -> None:
    if movement_type not in {"receipt", "issue", "damage", "adjustment"}:
        raise HTTPException(status_code=400, detail="Movement type must be receipt, issue, damage, or adjustment")


def _location_has_stock(db: Session, location_id: int) -> bool:
    total = (
        db.query(func.coalesce(func.sum(LocationStock.on_hand_quantity), 0))
        .filter(LocationStock.location_id == location_id)
        .scalar()
    )
    return _float(total) > 0


def _get_or_create_location_stock(db: Session, company_id: int, product: Product, location: WarehouseLocation) -> LocationStock:
    stock = (
        db.query(LocationStock)
        .filter(LocationStock.product_id == product.id, LocationStock.location_id == location.id)
        .first()
    )
    if not stock:
        stock = LocationStock(
            company_id=company_id,
            product_id=product.id,
            location_id=location.id,
            on_hand_quantity=0,
            unit_valuation=product.unit_valuation or 0,
            reorder_level=product.reorder_level,
        )
        db.add(stock)
        db.flush()
    return stock


def _reconcile_product_quantity(db: Session, product: Product) -> None:
    total = (
        db.query(func.coalesce(func.sum(LocationStock.on_hand_quantity), 0))
        .filter(LocationStock.product_id == product.id)
        .scalar()
    )
    product.on_hand_quantity = _float(total)


def _next_transfer_reference(db: Session, company_id: int) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"{DEFAULT_TRANSFER_PREFIX}{year}-"
    last = (
        db.query(LocationStockMovement.transfer_reference)
        .filter(
            LocationStockMovement.company_id == company_id,
            LocationStockMovement.transfer_reference.isnot(None),
            LocationStockMovement.transfer_reference.like(f"{prefix}%"),
        )
        .order_by(LocationStockMovement.id.desc())
        .first()
    )
    seq = 1
    if last and last[0]:
        try:
            seq = int(str(last[0]).split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _record_product_movement(
    db: Session,
    product: Product,
    user: User,
    movement_type: str,
    quantity: float,
    unit_value: float,
    movement_date: datetime,
    *,
    qty_before: float,
    qty_after: float,
    adjustment_direction: str | None = None,
    reason: str | None = None,
    notes: str | None = None,
    reference_number: str | None = None,
    allow_negative: bool = False,
) -> StockMovement:
    if movement_type == "adjustment":
        direction = adjustment_direction or DIRECTION_IN
    else:
        direction = MOVEMENT_DIRECTIONS[movement_type]

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
        reference_number=reference_number,
        source_module="warehouse",
        reason=reason,
        notes=notes,
        negative_override=allow_negative and qty_after < 0,
    )
    db.add(movement)
    product.unit_valuation = unit_value
    product.last_movement_at = movement_date
    return movement


def _apply_location_movement(
    db: Session,
    product: Product,
    location: WarehouseLocation,
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
    allow_negative: bool = False,
) -> tuple[LocationStockMovement, StockMovement | None]:
    _validate_movement_type(movement_type)
    if location.status != "active":
        raise HTTPException(status_code=400, detail="Only active locations can receive stock movements")
    if not product.inventory_tracked:
        raise HTTPException(status_code=400, detail="Product is not inventory-tracked")
    if product.status != "active":
        raise HTTPException(status_code=400, detail="Cannot move stock on inactive product")
    if not product.opening_recorded:
        raise HTTPException(status_code=400, detail="Record opening stock before warehouse movements")
    if movement_type in {"damage", "adjustment"} and not reason:
        raise HTTPException(status_code=400, detail="Reason is required for damage and adjustment movements")

    if movement_type == "adjustment":
        if adjustment_direction not in {DIRECTION_IN, DIRECTION_OUT}:
            raise HTTPException(status_code=400, detail="Adjustment direction must be in or out")
        direction = adjustment_direction
    else:
        direction = LOCATION_MOVEMENT_DIRECTIONS[movement_type]

    stock = _get_or_create_location_stock(db, product.company_id, product, location)
    qty_before = _float(stock.on_hand_quantity)
    delta = quantity if direction == DIRECTION_IN else -quantity
    qty_after = qty_before + delta

    if qty_after < 0 and not allow_negative:
        raise HTTPException(status_code=400, detail="Insufficient stock at this location")

    product_qty_before = _float(product.on_hand_quantity)

    stock.on_hand_quantity = qty_after
    stock.unit_valuation = unit_value
    stock.last_movement_at = movement_date

    loc_movement = LocationStockMovement(
        company_id=product.company_id,
        product_id=product.id,
        location_id=location.id,
        recorded_by_id=user.id,
        movement_type=movement_type,
        direction=direction,
        quantity=quantity,
        unit_value=unit_value,
        total_value=quantity * unit_value,
        quantity_before=qty_before,
        quantity_after=qty_after,
        movement_date=movement_date,
        reference_number=reference_number,
        reason=reason,
        notes=notes,
        negative_override=allow_negative and qty_after < 0,
    )
    db.add(loc_movement)

    _reconcile_product_quantity(db, product)
    product_qty_after = _float(product.on_hand_quantity)

    inv_type = INVENTORY_SYNC_TYPES[movement_type]
    stock_movement = _record_product_movement(
        db,
        product,
        user,
        inv_type,
        quantity,
        unit_value,
        movement_date,
        qty_before=product_qty_before,
        qty_after=product_qty_after,
        adjustment_direction=adjustment_direction,
        reason=reason,
        notes=notes,
        reference_number=reference_number,
        allow_negative=allow_negative,
    )
    db.flush()
    loc_movement.linked_stock_movement_id = stock_movement.id
    return loc_movement, stock_movement


@router.get("/location-types", response_model=list[WarehouseOptionResponse])
def location_types(_: User = Depends(require_permission("warehouses.view"))):
    return [WarehouseOptionResponse(value=t, label=LOCATION_TYPE_LABELS[t]) for t in LOCATION_TYPES]


@router.get("/location-statuses", response_model=list[WarehouseOptionResponse])
def location_statuses(_: User = Depends(require_permission("warehouses.view"))):
    return [WarehouseOptionResponse(value=s, label=LOCATION_STATUS_LABELS[s]) for s in LOCATION_STATUSES]


@router.get("/movement-types", response_model=list[WarehouseOptionResponse])
def movement_types(_: User = Depends(require_permission("warehouses.view"))):
    manual = ["receipt", "issue", "damage", "adjustment"]
    return [WarehouseOptionResponse(value=t, label=LOCATION_MOVEMENT_LABELS[t]) for t in manual]


@router.get("/stats/summary", response_model=WarehouseStatsResponse)
def stats(user: User = Depends(require_permission("warehouses.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    cache = _location_cache(db, company.id)

    stocks = (
        db.query(LocationStock)
        .options(joinedload(LocationStock.product), joinedload(LocationStock.location))
        .filter(LocationStock.company_id == company.id)
        .all()
    )
    total_value = sum(_stock_value(s.on_hand_quantity, s.unit_valuation) for s in stocks)

    locations = list(cache.values())
    active_wh = sum(1 for l in locations if l.location_type in {"warehouse", "store"} and l.status == "active")
    loc_with_stock_ids = {s.location_id for s in stocks if _float(s.on_hand_quantity) > 0}
    low_stock_locs: set[int] = set()
    branch_totals: dict[str, float] = {}
    wh_totals: dict[str, float] = {}

    for s in stocks:
        loc = cache.get(s.location_id)
        if not loc:
            continue
        val = _stock_value(s.on_hand_quantity, s.unit_valuation)
        branch = _branch_name(loc, cache) or "Unassigned"
        warehouse = _warehouse_name(loc, cache) or loc.name
        branch_totals[branch] = branch_totals.get(branch, 0) + val
        wh_totals[warehouse] = wh_totals.get(warehouse, 0) + val
        if _location_stock_status(s) in {"low_stock", "out_of_stock"}:
            low_stock_locs.add(s.location_id)

    transfer_outs = (
        db.query(LocationStockMovement)
        .options(
            joinedload(LocationStockMovement.product),
            joinedload(LocationStockMovement.location),
            joinedload(LocationStockMovement.recorded_by),
        )
        .filter(
            LocationStockMovement.company_id == company.id,
            LocationStockMovement.movement_type == "transfer_out",
        )
        .order_by(LocationStockMovement.movement_date.desc(), LocationStockMovement.id.desc())
        .limit(10)
        .all()
    )
    recent_transfers: list[WarehouseTransferResponse] = []
    for out_m in transfer_outs:
        in_m = (
            db.query(LocationStockMovement)
            .options(
                joinedload(LocationStockMovement.product),
                joinedload(LocationStockMovement.location),
                joinedload(LocationStockMovement.recorded_by),
            )
            .filter(
                LocationStockMovement.company_id == company.id,
                LocationStockMovement.transfer_reference == out_m.transfer_reference,
                LocationStockMovement.movement_type == "transfer_in",
            )
            .first()
        )
        if in_m:
            recent_transfers.append(_transfer_response(out_m, in_m, cache))

    recent = (
        db.query(LocationStockMovement)
        .options(
            joinedload(LocationStockMovement.product),
            joinedload(LocationStockMovement.location),
            joinedload(LocationStockMovement.recorded_by),
        )
        .filter(LocationStockMovement.company_id == company.id)
        .order_by(LocationStockMovement.movement_date.desc(), LocationStockMovement.id.desc())
        .limit(10)
        .all()
    )

    return WarehouseStatsResponse(
        total_stock_value=total_value,
        active_warehouses=active_wh,
        total_locations=len(locations),
        locations_with_stock=len(loc_with_stock_ids),
        low_stock_locations=len(low_stock_locs),
        stock_by_branch=[{"name": k, "value": v} for k, v in sorted(branch_totals.items(), key=lambda x: x[1], reverse=True)],
        stock_by_warehouse=[{"name": k, "value": v} for k, v in sorted(wh_totals.items(), key=lambda x: x[1], reverse=True)],
        recent_transfers=recent_transfers,
        recent_movements=[_movement_response(m, cache) for m in recent],
    )


@router.get("/locations", response_model=WarehouseLocationListResponse)
def list_locations(
    location_type: str | None = None,
    status: str | None = None,
    branch_id: int | None = None,
    warehouse_id: int | None = None,
    has_stock: bool | None = None,
    search: str | None = None,
    user: User = Depends(require_permission("warehouses.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    cache = _location_cache(db, company.id)
    query = db.query(WarehouseLocation).filter(WarehouseLocation.company_id == company.id)

    if location_type:
        _validate_location_type(location_type)
        query = query.filter(WarehouseLocation.location_type == location_type)
    if status:
        _validate_location_status(status)
        query = query.filter(WarehouseLocation.status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(WarehouseLocation.name.ilike(term), WarehouseLocation.location_code.ilike(term)))

    locations = query.order_by(WarehouseLocation.name).all()

    stock_by_loc: dict[int, list[LocationStock]] = {}
    for s in db.query(LocationStock).filter(LocationStock.company_id == company.id).all():
        stock_by_loc.setdefault(s.location_id, []).append(s)

    child_counts: dict[int, int] = {}
    for loc in locations:
        if loc.parent_id:
            child_counts[loc.parent_id] = child_counts.get(loc.parent_id, 0) + 1

    def _in_branch(loc: WarehouseLocation) -> bool:
        if not branch_id:
            return True
        return loc.id == branch_id or any(a.id == branch_id for a in _ancestors(loc, cache))

    def _in_warehouse(loc: WarehouseLocation) -> bool:
        if not warehouse_id:
            return True
        return loc.id == warehouse_id or any(a.id == warehouse_id for a in _ancestors(loc, cache))

    items: list[WarehouseLocationResponse] = []
    for loc in locations:
        if not _in_branch(loc) or not _in_warehouse(loc):
            continue
        rows = stock_by_loc.get(loc.id, [])
        totals = {
            "sku_count": len(rows),
            "total_on_hand": sum(_float(r.on_hand_quantity) for r in rows),
            "total_stock_value": sum(_stock_value(r.on_hand_quantity, r.unit_valuation) for r in rows),
            "low_stock_count": sum(1 for r in rows if _location_stock_status(r) == "low_stock"),
        }
        if has_stock is True and totals["total_on_hand"] <= 0:
            continue
        if has_stock is False and totals["total_on_hand"] > 0:
            continue
        loc.parent = cache.get(loc.parent_id) if loc.parent_id else None
        items.append(
            _location_response(loc, cache=cache, totals=totals, child_count=child_counts.get(loc.id, 0))
        )

    active_wh = sum(1 for l in locations if l.location_type in {"warehouse", "store"} and l.status == "active")
    with_stock = sum(1 for i in items if i.total_on_hand > 0)
    below_reorder = sum(i.low_stock_count for i in items)

    return WarehouseLocationListResponse(
        items=items,
        total=len(items),
        summary={
            "total_locations": len(locations),
            "active_warehouses": active_wh,
            "locations_with_stock": with_stock,
            "below_reorder": below_reorder,
        },
    )


@router.post("/locations", response_model=WarehouseLocationResponse)
def create_location(
    body: WarehouseLocationCreateRequest,
    request: Request,
    user: User = Depends(require_permission("warehouses.manage_locations")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    _validate_location_type(body.location_type)
    _validate_location_status(body.status)

    if body.location_type == "branch" and body.parent_id:
        raise HTTPException(status_code=400, detail="Branch locations cannot have a parent")
    if body.location_type != "branch" and not body.parent_id:
        raise HTTPException(status_code=400, detail="Parent location is required")

    parent = None
    if body.parent_id:
        parent = _get_location(db, body.parent_id, company.id)

    existing = (
        db.query(WarehouseLocation)
        .filter(WarehouseLocation.company_id == company.id, WarehouseLocation.location_code == body.location_code.strip())
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Location code already exists")

    location = WarehouseLocation(
        company_id=company.id,
        parent_id=body.parent_id,
        created_by_id=user.id,
        location_code=body.location_code.strip(),
        name=body.name.strip(),
        location_type=body.location_type,
        status=body.status,
        address=body.address,
        notes=body.notes,
        is_default_receiving=body.is_default_receiving,
        is_default_dispatch=body.is_default_dispatch,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    location.parent = parent
    cache = _location_cache(db, company.id)

    log_activity(
        db,
        "warehouse_location_created",
        user_id=user.id,
        email=user.email,
        details=f"Created location {location.name}",
        ip_address=get_client_ip(request),
    )
    db.commit()

    return _location_response(location, cache=cache)


@router.get("/locations/{location_id}", response_model=WarehouseLocationDetailResponse)
def get_location(
    location_id: int,
    user: User = Depends(require_permission("warehouses.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    location = _get_location(db, location_id, company.id)
    cache = _location_cache(db, company.id)
    location.parent = cache.get(location.parent_id) if location.parent_id else None

    children = (
        db.query(WarehouseLocation)
        .filter(WarehouseLocation.parent_id == location.id)
        .order_by(WarehouseLocation.name)
        .all()
    )
    totals = _location_totals(db, location.id)
    child_responses = [
        _location_response(c, cache=cache, totals=_location_totals(db, c.id)) for c in children
    ]

    stocks = (
        db.query(LocationStock)
        .options(joinedload(LocationStock.product), joinedload(LocationStock.location))
        .filter(LocationStock.location_id == location.id)
        .order_by(LocationStock.on_hand_quantity.desc())
        .all()
    )
    movements = (
        db.query(LocationStockMovement)
        .options(
            joinedload(LocationStockMovement.product),
            joinedload(LocationStockMovement.location),
            joinedload(LocationStockMovement.recorded_by),
        )
        .filter(LocationStockMovement.location_id == location.id)
        .order_by(LocationStockMovement.movement_date.desc(), LocationStockMovement.id.desc())
        .limit(20)
        .all()
    )

    base = _location_response(location, cache=cache, totals=totals, child_count=len(children))
    return WarehouseLocationDetailResponse(
        **base.model_dump(),
        children=child_responses,
        stock=[_stock_response(s, cache) for s in stocks],
        recent_movements=[_movement_response(m, cache) for m in movements],
    )


@router.patch("/locations/{location_id}", response_model=WarehouseLocationResponse)
def update_location(
    location_id: int,
    body: WarehouseLocationUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("warehouses.manage_locations")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    location = _get_location(db, location_id, company.id)

    if body.status:
        _validate_location_status(body.status)
        if body.status in {"inactive", "closed"} and _location_has_stock(db, location.id):
            raise HTTPException(status_code=400, detail="Cannot deactivate location with remaining stock")

    if body.name is not None:
        location.name = body.name.strip()
    if body.status is not None:
        location.status = body.status
    if body.address is not None:
        location.address = body.address
    if body.notes is not None:
        location.notes = body.notes
    if body.is_default_receiving is not None:
        location.is_default_receiving = body.is_default_receiving
    if body.is_default_dispatch is not None:
        location.is_default_dispatch = body.is_default_dispatch

    db.commit()
    db.refresh(location)
    cache = _location_cache(db, company.id)
    location.parent = cache.get(location.parent_id) if location.parent_id else None

    log_activity(
        db,
        "warehouse_location_updated",
        user_id=user.id,
        email=user.email,
        details=f"Updated location {location.name}",
        ip_address=get_client_ip(request),
    )
    db.commit()

    return _location_response(location, cache=cache, totals=_location_totals(db, location.id))


@router.get("/stock", response_model=LocationStockListResponse)
def list_stock(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    branch_id: int | None = None,
    warehouse_id: int | None = None,
    location_id: int | None = None,
    low_stock: bool | None = None,
    out_of_stock: bool | None = None,
    category: str | None = None,
    search: str | None = None,
    user: User = Depends(require_permission("warehouses.view_stock")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    cache = _location_cache(db, company.id)
    query = (
        db.query(LocationStock)
        .options(joinedload(LocationStock.product), joinedload(LocationStock.location))
        .filter(LocationStock.company_id == company.id)
    )
    if location_id:
        query = query.filter(LocationStock.location_id == location_id)
    if category:
        query = query.join(Product).filter(Product.category == category)
    if search:
        term = f"%{search.strip()}%"
        query = query.join(Product).filter(
            or_(Product.name.ilike(term), Product.service_code.ilike(term))
        )

    rows = query.all()
    items: list[LocationStockResponse] = []
    for stock in rows:
        loc = cache.get(stock.location_id)
        if not loc:
            continue
        if branch_id and not (loc.id == branch_id or any(a.id == branch_id for a in _ancestors(loc, cache))):
            continue
        if warehouse_id and not (loc.id == warehouse_id or any(a.id == warehouse_id for a in _ancestors(loc, cache))):
            continue
        status = _location_stock_status(stock)
        if low_stock and status != "low_stock":
            continue
        if out_of_stock and status != "out_of_stock":
            continue
        stock.location = loc
        items.append(_stock_response(stock, cache))

    items.sort(key=lambda x: x.stock_value, reverse=True)
    total = len(items)
    start = (page - 1) * limit
    page_items = items[start : start + limit]

    return LocationStockListResponse(items=page_items, total=total, page=page, limit=limit)


@router.get("/stock/product/{product_id}", response_model=LocationStockListResponse)
def product_stock_by_location(
    product_id: int,
    user: User = Depends(require_permission("warehouses.view_stock")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    _get_product(db, product_id, company.id)
    cache = _location_cache(db, company.id)
    stocks = (
        db.query(LocationStock)
        .options(joinedload(LocationStock.product), joinedload(LocationStock.location))
        .filter(LocationStock.company_id == company.id, LocationStock.product_id == product_id)
        .all()
    )
    items = [_stock_response(s, cache) for s in stocks if _float(s.on_hand_quantity) > 0 or True]
    return LocationStockListResponse(items=items, total=len(items), page=1, limit=max(len(items), 1))


@router.get("/movements", response_model=LocationStockMovementListResponse)
def list_movements(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    movement_type: str | None = None,
    location_id: int | None = None,
    product_id: int | None = None,
    search: str | None = None,
    user: User = Depends(require_permission("warehouses.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    cache = _location_cache(db, company.id)
    query = (
        db.query(LocationStockMovement)
        .options(
            joinedload(LocationStockMovement.product),
            joinedload(LocationStockMovement.location),
            joinedload(LocationStockMovement.recorded_by),
        )
        .filter(LocationStockMovement.company_id == company.id)
    )
    if movement_type:
        query = query.filter(LocationStockMovement.movement_type == movement_type)
    if location_id:
        query = query.filter(LocationStockMovement.location_id == location_id)
    if product_id:
        query = query.filter(LocationStockMovement.product_id == product_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.join(Product).filter(
            or_(Product.name.ilike(term), Product.service_code.ilike(term))
        )

    total = query.count()
    movements = (
        query.order_by(LocationStockMovement.movement_date.desc(), LocationStockMovement.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return LocationStockMovementListResponse(
        items=[_movement_response(m, cache) for m in movements],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/movements", response_model=LocationStockMovementResponse)
def record_movement(
    body: WarehouseRecordMovementRequest,
    request: Request,
    user: User = Depends(require_permission("warehouses.view")),
    db: Session = Depends(get_db),
):
    perm = MOVEMENT_PERMISSIONS.get(body.movement_type)
    if not perm or not role_has_permission(db, user.role, perm):
        raise HTTPException(status_code=403, detail="Insufficient permissions for this movement type")

    company = get_current_company(db, user)
    product = _get_product(db, body.product_id, company.id)
    location = _get_location(db, body.location_id, company.id)

    allow_negative = False
    if body.movement_type in {"issue", "damage", "adjustment"} and body.adjustment_direction == DIRECTION_OUT:
        allow_negative = role_has_permission(db, user.role, "warehouses.override_negative")
    elif body.movement_type in {"issue", "damage"}:
        allow_negative = role_has_permission(db, user.role, "warehouses.override_negative")

    if body.movement_type == "adjustment" and body.reason not in ADJUSTMENT_REASONS:
        pass
    if body.movement_type == "damage" and body.reason not in DAMAGE_REASONS:
        pass

    movement, _ = _apply_location_movement(
        db,
        product,
        location,
        user,
        body.movement_type,
        body.quantity,
        body.unit_valuation,
        body.movement_date,
        adjustment_direction=body.adjustment_direction,
        reason=body.reason,
        notes=body.notes,
        reference_number=body.reference_number,
        allow_negative=allow_negative,
    )

    log_activity(
        db,
        f"warehouse_{body.movement_type}_recorded",
        user_id=user.id,
        email=user.email,
        details=f"{body.movement_type} {body.quantity} of {product.name} at {location.name}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(movement)

    cache = _location_cache(db, company.id)
    return _movement_response(movement, cache)


@router.post("/transfers", response_model=WarehouseTransferResponse)
def transfer_stock(
    body: WarehouseTransferRequest,
    request: Request,
    user: User = Depends(require_permission("warehouses.transfer")),
    db: Session = Depends(get_db),
):
    if body.source_location_id == body.destination_location_id:
        raise HTTPException(status_code=400, detail="Source and destination must be different")

    company = get_current_company(db, user)
    product = _get_product(db, body.product_id, company.id)
    source = _get_location(db, body.source_location_id, company.id)
    dest = _get_location(db, body.destination_location_id, company.id)

    if source.status != "active" or dest.status != "active":
        raise HTTPException(status_code=400, detail="Both locations must be active")
    if not product.inventory_tracked:
        raise HTTPException(status_code=400, detail="Product is not inventory-tracked")
    if not product.opening_recorded:
        raise HTTPException(status_code=400, detail="Record opening stock before transfers")

    allow_negative = role_has_permission(db, user.role, "warehouses.override_negative")
    source_stock = _get_or_create_location_stock(db, company.id, product, source)
    qty_before_src = _float(source_stock.on_hand_quantity)
    if qty_before_src < body.quantity and not allow_negative:
        raise HTTPException(status_code=400, detail="Insufficient stock at source location")

    dest_stock = _get_or_create_location_stock(db, company.id, product, dest)
    qty_before_dest = _float(dest_stock.on_hand_quantity)
    unit_value = _float(source_stock.unit_valuation or product.unit_valuation)
    transfer_ref = _next_transfer_reference(db, company.id)

    qty_after_src = qty_before_src - body.quantity
    qty_after_dest = qty_before_dest + body.quantity

    source_stock.on_hand_quantity = qty_after_src
    source_stock.last_movement_at = body.movement_date
    dest_stock.on_hand_quantity = qty_after_dest
    dest_stock.unit_valuation = unit_value
    dest_stock.last_movement_at = body.movement_date

    out_m = LocationStockMovement(
        company_id=company.id,
        product_id=product.id,
        location_id=source.id,
        recorded_by_id=user.id,
        movement_type="transfer_out",
        direction=DIRECTION_OUT,
        quantity=body.quantity,
        unit_value=unit_value,
        total_value=body.quantity * unit_value,
        quantity_before=qty_before_src,
        quantity_after=qty_after_src,
        movement_date=body.movement_date,
        transfer_reference=transfer_ref,
        reference_number=body.reference_number,
        notes=body.notes,
        negative_override=allow_negative and qty_after_src < 0,
    )
    in_m = LocationStockMovement(
        company_id=company.id,
        product_id=product.id,
        location_id=dest.id,
        recorded_by_id=user.id,
        movement_type="transfer_in",
        direction=DIRECTION_IN,
        quantity=body.quantity,
        unit_value=unit_value,
        total_value=body.quantity * unit_value,
        quantity_before=qty_before_dest,
        quantity_after=qty_after_dest,
        movement_date=body.movement_date,
        transfer_reference=transfer_ref,
        reference_number=body.reference_number,
        notes=body.notes,
    )
    db.add(out_m)
    db.add(in_m)
    _reconcile_product_quantity(db, product)

    log_activity(
        db,
        "warehouse_transfer_completed",
        user_id=user.id,
        email=user.email,
        details=f"Transferred {body.quantity} {product.name} from {source.name} to {dest.name} ({transfer_ref})",
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(out_m)
    db.refresh(in_m)

    cache = _location_cache(db, company.id)
    return _transfer_response(out_m, in_m, cache)


@router.get("/transfers", response_model=WarehouseTransferListResponse)
def list_transfers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    product_id: int | None = None,
    user: User = Depends(require_permission("warehouses.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    cache = _location_cache(db, company.id)
    query = (
        db.query(LocationStockMovement)
        .options(
            joinedload(LocationStockMovement.product),
            joinedload(LocationStockMovement.location),
            joinedload(LocationStockMovement.recorded_by),
        )
        .filter(
            LocationStockMovement.company_id == company.id,
            LocationStockMovement.movement_type == "transfer_out",
        )
    )
    if product_id:
        query = query.filter(LocationStockMovement.product_id == product_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(LocationStockMovement.transfer_reference.ilike(term))

    total = query.count()
    outs = (
        query.order_by(LocationStockMovement.movement_date.desc(), LocationStockMovement.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items: list[WarehouseTransferResponse] = []
    for out_m in outs:
        in_m = (
            db.query(LocationStockMovement)
            .options(
                joinedload(LocationStockMovement.product),
                joinedload(LocationStockMovement.location),
                joinedload(LocationStockMovement.recorded_by),
            )
            .filter(
                LocationStockMovement.company_id == company.id,
                LocationStockMovement.transfer_reference == out_m.transfer_reference,
                LocationStockMovement.movement_type == "transfer_in",
            )
            .first()
        )
        if in_m:
            items.append(_transfer_response(out_m, in_m, cache))

    return WarehouseTransferListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/low-stock", response_model=LocationStockListResponse)
def low_stock(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("warehouses.view_stock")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    cache = _location_cache(db, company.id)
    stocks = (
        db.query(LocationStock)
        .options(joinedload(LocationStock.product), joinedload(LocationStock.location))
        .filter(LocationStock.company_id == company.id)
        .all()
    )
    items = [_stock_response(s, cache) for s in stocks if _location_stock_status(s) == "low_stock"]
    items.sort(key=lambda x: x.on_hand_quantity)
    total = len(items)
    start = (page - 1) * limit
    return LocationStockListResponse(items=items[start : start + limit], total=total, page=page, limit=limit)
