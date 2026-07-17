from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_current_user, get_db
from inventory_config import DIRECTION_IN, DIRECTION_OUT, OUT_MOVEMENT_TYPES
from models import Company, Product, StockMovement, User
from permissions import role_has_permission
from routers.inventory_router import _apply_movement, _float, _get_company, _get_product, _movement_response
from schemas import (
    StockMovementExtendedListResponse,
    StockMovementExtendedResponse,
    StockMovementReasonOption,
    StockMovementRecordRequest,
    StockMovementStatsResponse,
)
from stock_movements_config import (
    NOTES_REQUIRED_REASONS,
    REFERENCE_REQUIRED_REASONS,
    STOCK_IN_MOVEMENT_MAP,
    STOCK_IN_REASON_LABELS,
    STOCK_IN_REASONS,
    STOCK_OUT_MOVEMENT_MAP,
    STOCK_OUT_REASON_LABELS,
    STOCK_OUT_REASONS,
    DAMAGE_REASON_DEFAULT,
)

router = APIRouter(prefix="/stock-movements", tags=["stock-movements"])


def _require_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if role_has_permission(db, user.role, "stock_movements.view") or role_has_permission(db, user.role, "inventory.view"):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_record_in(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    perms = ("stock_movements.record_in", "inventory.record_purchase", "inventory.adjust", "inventory.record_opening")
    if any(role_has_permission(db, user.role, p) for p in perms):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_record_out(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    perms = ("stock_movements.record_out", "inventory.record_sale", "inventory.record_damage", "inventory.adjust")
    if any(role_has_permission(db, user.role, p) for p in perms):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _movement_number(m: StockMovement) -> str:
    year = m.movement_date.year if m.movement_date else datetime.now(timezone.utc).year
    return f"SM-{year}-{m.id:05d}"


def _reason_label(reason: str | None, direction: str) -> str | None:
    if not reason:
        return None
    if direction == DIRECTION_IN:
        return STOCK_IN_REASON_LABELS.get(reason, reason.replace("_", " ").title())
    return STOCK_OUT_REASON_LABELS.get(reason, reason.replace("_", " ").title())


def _extended_response(m: StockMovement) -> StockMovementExtendedResponse:
    base = _movement_response(m)
    return StockMovementExtendedResponse(
        **base.model_dump(),
        movement_number=_movement_number(m),
        reason_label=_reason_label(m.reason, m.direction),
    )


def _get_movement(db: Session, movement_id: int, company_id: int) -> StockMovement:
    movement = (
        db.query(StockMovement)
        .options(joinedload(StockMovement.product), joinedload(StockMovement.recorded_by))
        .filter(StockMovement.id == movement_id, StockMovement.company_id == company_id)
        .first()
    )
    if not movement:
        raise HTTPException(status_code=404, detail="Stock movement not found")
    return movement


def _validate_reason(reason: str, direction: str) -> None:
    allowed = STOCK_IN_REASONS if direction == DIRECTION_IN else STOCK_OUT_REASONS
    if reason not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid reason for stock {direction}")


def _resolve_movement(reason: str, direction: str) -> tuple[str, str | None]:
    mapping = STOCK_IN_MOVEMENT_MAP if direction == DIRECTION_IN else STOCK_OUT_MOVEMENT_MAP
    return mapping[reason]


def _check_permission(db: Session, user: User, movement_type: str, direction: str) -> None:
    if movement_type == "purchase" or (movement_type == "adjustment" and direction == DIRECTION_IN):
        perm = "stock_movements.record_in"
        fallback = "inventory.record_purchase"
    elif movement_type == "sale" or movement_type == "damage" or (movement_type == "adjustment" and direction == DIRECTION_OUT):
        perm = "stock_movements.record_out"
        fallback = "inventory.record_sale" if movement_type == "sale" else "inventory.record_damage"
        if movement_type == "adjustment":
            fallback = "inventory.adjust"
    else:
        perm = "stock_movements.record_in" if direction == DIRECTION_IN else "stock_movements.record_out"
        fallback = "inventory.adjust"
    if not role_has_permission(db, user.role, perm) and not role_has_permission(db, user.role, fallback):
        raise HTTPException(status_code=403, detail="You do not have permission to record this movement")


def _record(
    db: Session,
    company: Company,
    user: User,
    payload: StockMovementRecordRequest,
    direction: str,
    request: Request,
) -> StockMovementExtendedResponse:
    if payload.movement_date > datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Movement date cannot be in the future")
    _validate_reason(payload.reason, direction)
    if payload.reason in REFERENCE_REQUIRED_REASONS and not (payload.reference_number or "").strip():
        raise HTTPException(status_code=400, detail="Reference is required for this reason")
    if payload.reason in NOTES_REQUIRED_REASONS and not (payload.notes or "").strip():
        raise HTTPException(status_code=400, detail="Notes are required when reason is Other")

    product = _get_product(db, payload.product_id, company.id)
    movement_type, adjustment_direction = _resolve_movement(payload.reason, direction)
    _check_permission(db, user, movement_type, direction)

    allow_negative = False
    if direction == DIRECTION_OUT and movement_type in OUT_MOVEMENT_TYPES | {"adjustment"}:
        if _float(product.on_hand_quantity) < payload.quantity:
            if role_has_permission(db, user.role, "stock_movements.override_negative") or role_has_permission(
                db, user.role, "inventory.override_negative"
            ):
                allow_negative = True
            else:
                raise HTTPException(status_code=400, detail="Insufficient stock for this movement")

    stored_reason = payload.reason
    if movement_type == "damage":
        stored_reason = DAMAGE_REASON_DEFAULT

    movement = _apply_movement(
        db,
        product,
        user,
        movement_type,
        payload.quantity,
        payload.unit_valuation if payload.unit_valuation is not None else _float(product.unit_valuation),
        payload.movement_date,
        adjustment_direction=adjustment_direction,
        reason=stored_reason if movement_type in {"damage", "adjustment"} else payload.reason,
        notes=payload.notes or _reason_label(payload.reason, direction),
        reference_number=payload.reference_number,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        source_module=payload.source_module or "stock_movements",
        allow_negative=allow_negative,
    )
    movement.reason = payload.reason

    db.commit()
    db.refresh(movement)
    movement = _get_movement(db, movement.id, company.id)

    action = "stock_movement_in_recorded" if direction == DIRECTION_IN else "stock_movement_out_recorded"
    log_activity(
        db,
        action,
        user_id=user.id,
        email=user.email,
        details=f"{payload.reason} {payload.quantity} on {product.name}",
        ip_address=get_client_ip(request),
    )
    return _extended_response(movement)


@router.get("/reasons/in", response_model=list[StockMovementReasonOption])
def reasons_in(_: User = Depends(_require_view)):
    return [StockMovementReasonOption(value=r, label=STOCK_IN_REASON_LABELS[r]) for r in STOCK_IN_REASONS]


@router.get("/reasons/out", response_model=list[StockMovementReasonOption])
def reasons_out(_: User = Depends(_require_view)):
    return [StockMovementReasonOption(value=r, label=STOCK_OUT_REASON_LABELS[r]) for r in STOCK_OUT_REASONS]


@router.get("/stats/summary", response_model=StockMovementStatsResponse)
def stats(user: User = Depends(_require_view), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())

    today = db.query(StockMovement).filter(StockMovement.company_id == company.id, StockMovement.movement_date >= day_start).all()
    in_qty = sum(_float(m.quantity) for m in today if m.direction == DIRECTION_IN)
    out_qty = sum(_float(m.quantity) for m in today if m.direction == DIRECTION_OUT)

    week_out: dict[int, float] = {}
    week_movements = db.query(StockMovement).filter(
        StockMovement.company_id == company.id,
        StockMovement.direction == DIRECTION_OUT,
        StockMovement.movement_date >= week_start,
    ).all()
    for m in week_movements:
        week_out[m.product_id] = week_out.get(m.product_id, 0) + _float(m.quantity)

    top_product_id = max(week_out, key=week_out.get) if week_out else None
    top_product_name = None
    top_qty = 0.0
    if top_product_id:
        p = db.query(Product).filter(Product.id == top_product_id).first()
        top_product_name = p.name if p else None
        top_qty = week_out[top_product_id]

    recent = (
        db.query(StockMovement)
        .options(joinedload(StockMovement.product), joinedload(StockMovement.recorded_by))
        .filter(StockMovement.company_id == company.id)
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
        .limit(10)
        .all()
    )

    return StockMovementStatsResponse(
        stock_in_today=in_qty,
        stock_out_today=out_qty,
        net_change_today=in_qty - out_qty,
        movement_count_today=len(today),
        top_out_product_name=top_product_name,
        top_out_product_qty=top_qty,
        recent_movements=[_extended_response(m) for m in recent],
    )


@router.get("", response_model=StockMovementExtendedListResponse)
def list_movements(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    direction: str | None = None,
    product_id: int | None = None,
    reason: str | None = None,
    recorded_by_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    user: User = Depends(_require_view),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(StockMovement)
        .options(joinedload(StockMovement.product), joinedload(StockMovement.recorded_by))
        .filter(StockMovement.company_id == company.id)
    )
    if direction in {DIRECTION_IN, DIRECTION_OUT}:
        query = query.filter(StockMovement.direction == direction)
    if product_id:
        query = query.filter(StockMovement.product_id == product_id)
    if reason:
        query = query.filter(StockMovement.reason == reason)
    if recorded_by_id:
        query = query.filter(StockMovement.recorded_by_id == recorded_by_id)
    if date_from:
        query = query.filter(StockMovement.movement_date >= date_from)
    if date_to:
        query = query.filter(StockMovement.movement_date <= date_to)
    if search:
        term = f"%{search.strip()}%"
        query = query.join(Product).filter(
            or_(
                Product.name.ilike(term),
                Product.service_code.ilike(term),
                StockMovement.reference_number.ilike(term),
                StockMovement.notes.ilike(term),
            )
        )
    total = query.count()
    items = query.order_by(StockMovement.movement_date.desc(), StockMovement.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return StockMovementListResponse(
        items=[_extended_response(m) for m in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{movement_id}", response_model=StockMovementExtendedResponse)
def get_movement(
    movement_id: int,
    user: User = Depends(_require_view),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    return _extended_response(_get_movement(db, movement_id, company.id))


@router.post("/in", response_model=StockMovementExtendedResponse, status_code=201)
def record_stock_in(
    payload: StockMovementRecordRequest,
    request: Request,
    user: User = Depends(_require_record_in),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    return _record(db, company, user, payload, DIRECTION_IN, request)


@router.post("/out", response_model=StockMovementExtendedResponse, status_code=201)
def record_stock_out(
    payload: StockMovementRecordRequest,
    request: Request,
    user: User = Depends(_require_record_out),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    return _record(db, company, user, payload, DIRECTION_OUT, request)
