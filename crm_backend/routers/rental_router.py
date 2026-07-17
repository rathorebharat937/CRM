"""Rental Management API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import (
    Company,
    Contact,
    RentalAsset,
    RentalContract,
    RentalContractLine,
    RentalDeposit,
    RentalInvoice,
    RentalSettings,
    User,
)
from rental_config import (
    ASSET_STATUSES,
    DEFAULT_AUTO_INVOICE_MODE,
    DEFAULT_CONTRACT_PREFIX,
    DEFAULT_DEPOSIT_PERCENT,
    DEFAULT_GRACE_HOURS,
    DEFAULT_LATE_FEE_PER_DAY,
    DEFAULT_NOTIFY_ROLES,
    DEFAULT_RATE_BASIS,
)
from rental_schemas import (
    AvailabilityCheckResponse,
    CalendarEvent,
    CalendarResponse,
    ContractCancelRequest,
    ContractCloseRequest,
    ContractCreateRequest,
    ContractDispatchRequest,
    ContractListItem,
    ContractListResponse,
    ContractResponse,
    ContractReturnRequest,
    ContractScheduleReturnRequest,
    DepositRecordRequest,
    DepositRecordResponse,
    RentalAssetCreateRequest,
    RentalAssetResponse,
    RentalAssetUpdateRequest,
    RentalDashboardResponse,
    RentalInvoiceLink,
    RentalSettingsResponse,
    RentalSettingsUpdateRequest,
    ContractLineResponse,
)
from services.rental_service import (
    check_availability,
    compute_contract_totals,
    compute_late_fee,
    compute_line_pricing,
    create_contract_invoice,
    deposit_held,
    generate_contract_number,
    rental_days,
    send_rental_reminders,
    sync_deposit_totals,
    unit_rate_for_basis,
    validate_deposit_type,
    validate_rate_basis,
    validate_return_condition,
)

router = APIRouter(prefix="/rental", tags=["rental"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)




def _get_settings(db: Session, company: Company) -> RentalSettings:
    settings = db.query(RentalSettings).filter(RentalSettings.company_id == company.id).first()
    if settings:
        return settings
    settings = RentalSettings(
        company_id=company.id,
        is_enabled=True,
        contract_prefix=DEFAULT_CONTRACT_PREFIX,
        default_rate_basis=DEFAULT_RATE_BASIS,
        default_deposit_percent=DEFAULT_DEPOSIT_PERCENT,
        late_fee_per_day=DEFAULT_LATE_FEE_PER_DAY,
        grace_hours_after_due=DEFAULT_GRACE_HOURS,
        auto_invoice_mode=DEFAULT_AUTO_INVOICE_MODE,
        notify_roles_json=DEFAULT_NOTIFY_ROLES,
    )
    db.add(settings)
    db.flush()
    return settings


def _require_enabled(settings: RentalSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="Rental module is not enabled")


def _settings_response(settings: RentalSettings) -> RentalSettingsResponse:
    return RentalSettingsResponse(
        is_enabled=settings.is_enabled,
        contract_prefix=settings.contract_prefix or DEFAULT_CONTRACT_PREFIX,
        default_rate_basis=settings.default_rate_basis or DEFAULT_RATE_BASIS,
        default_deposit_percent=_float(settings.default_deposit_percent),
        late_fee_per_day=_float(settings.late_fee_per_day),
        grace_hours_after_due=int(settings.grace_hours_after_due or DEFAULT_GRACE_HOURS),
        auto_invoice_mode=settings.auto_invoice_mode or DEFAULT_AUTO_INVOICE_MODE,
        require_deposit_before_delivery=bool(settings.require_deposit_before_delivery),
        notify_roles_json=settings.notify_roles_json or [],
        allow_overbook=bool(settings.allow_overbook),
    )


def _asset_response(asset: RentalAsset) -> RentalAssetResponse:
    return RentalAssetResponse(
        id=asset.id,
        asset_code=asset.asset_code,
        name=asset.name,
        description=asset.description,
        category=asset.category,
        product_id=asset.product_id,
        quantity_available=int(asset.quantity_available or 1),
        rate_daily=_float(asset.rate_daily) if asset.rate_daily is not None else None,
        rate_weekly=_float(asset.rate_weekly) if asset.rate_weekly is not None else None,
        rate_monthly=_float(asset.rate_monthly) if asset.rate_monthly is not None else None,
        gst_rate=_float(asset.gst_rate),
        deposit_amount=_float(asset.deposit_amount) if asset.deposit_amount is not None else None,
        status=asset.status,
        location_notes=asset.location_notes,
        sort_order=int(asset.sort_order or 0),
    )


def _line_response(line: RentalContractLine) -> ContractLineResponse:
    asset = line.rental_asset
    return ContractLineResponse(
        id=line.id,
        rental_asset_id=line.rental_asset_id,
        asset_name=asset.name if asset else None,
        asset_code=asset.asset_code if asset else None,
        quantity=int(line.quantity or 1),
        rate_basis=line.rate_basis,
        unit_rate=_float(line.unit_rate),
        line_days=int(line.line_days or 1),
        line_subtotal=_float(line.line_subtotal),
        gst_rate=_float(line.gst_rate),
        line_total=_float(line.line_total),
        return_condition=line.return_condition,
        damage_notes=line.damage_notes,
        damage_charge=_float(line.damage_charge) if line.damage_charge is not None else None,
    )


def _contract_list_item(contract: RentalContract) -> ContractListItem:
    held = _float(deposit_held(contract))
    settled = contract.status == "closed" or held <= 0
    return ContractListItem(
        id=contract.id,
        contract_number=contract.contract_number,
        contact_id=contract.contact_id,
        contact_name=contract.contact.name if contract.contact else None,
        status=contract.status,
        rate_basis=contract.rate_basis,
        rental_start=contract.rental_start,
        rental_end=contract.rental_end,
        grand_total=_float(contract.grand_total),
        deposit_required=_float(contract.deposit_required),
        deposit_received=_float(contract.deposit_received),
        deposit_settled=settled,
    )


def _load_contract(db: Session, company_id: int, contract_id: int) -> RentalContract:
    contract = (
        db.query(RentalContract)
        .options(
            joinedload(RentalContract.contact),
            joinedload(RentalContract.lines).joinedload(RentalContractLine.rental_asset),
            joinedload(RentalContract.deposits),
            joinedload(RentalContract.rental_invoices).joinedload(RentalInvoice.invoice),
        )
        .filter(RentalContract.id == contract_id, RentalContract.company_id == company_id)
        .first()
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


def _contract_response(contract: RentalContract, conflicts: list[str] | None = None) -> ContractResponse:
    deposits = [
        DepositRecordResponse(
            id=d.id,
            type=d.type,
            amount=_float(d.amount),
            payment_method=d.payment_method,
            reference=d.reference,
            notes=d.notes,
            recorded_at=d.recorded_at,
        )
        for d in sorted(contract.deposits or [], key=lambda x: x.recorded_at or _utcnow(), reverse=True)
    ]
    invoices = []
    for link in sorted(contract.rental_invoices or [], key=lambda x: x.generated_at or _utcnow(), reverse=True):
        inv = link.invoice
        invoices.append(
            RentalInvoiceLink(
                id=link.id,
                invoice_id=link.invoice_id,
                invoice_number=inv.invoice_number if inv else None,
                invoice_status=inv.status if inv else None,
                invoice_type=link.invoice_type,
                grand_total=_float(inv.grand_total) if inv else None,
                generated_at=link.generated_at,
            )
        )
    return ContractResponse(
        id=contract.id,
        contract_number=contract.contract_number,
        contact_id=contract.contact_id,
        contact_name=contract.contact.name if contract.contact else None,
        status=contract.status,
        rate_basis=contract.rate_basis,
        rental_start=contract.rental_start,
        rental_end=contract.rental_end,
        actual_return_at=contract.actual_return_at,
        delivery_address=contract.delivery_address,
        delivery_contact_name=contract.delivery_contact_name,
        delivery_contact_phone=contract.delivery_contact_phone,
        delivery_scheduled_at=contract.delivery_scheduled_at,
        delivery_completed_at=contract.delivery_completed_at,
        return_scheduled_at=contract.return_scheduled_at,
        return_completed_at=contract.return_completed_at,
        subtotal=_float(contract.subtotal),
        deposit_required=_float(contract.deposit_required),
        deposit_received=_float(contract.deposit_received),
        deposit_refunded=_float(contract.deposit_refunded),
        deposit_deducted=_float(contract.deposit_deducted),
        deposit_held=_float(deposit_held(contract)),
        late_fee_total=_float(contract.late_fee_total),
        damage_charge_total=_float(contract.damage_charge_total),
        grand_total=_float(contract.grand_total),
        notes=contract.notes,
        cancellation_reason=contract.cancellation_reason,
        lines=[_line_response(ln) for ln in contract.lines or []],
        deposits=deposits,
        invoices=invoices,
        availability_conflicts=conflicts or [],
    )


def _build_contract_lines(
    db: Session,
    company: Company,
    contract: RentalContract,
    payload: ContractCreateRequest,
    settings: RentalSettings,
) -> tuple[list[RentalContractLine], dict[int, RentalAsset], list[str]]:
    rate_basis = payload.rate_basis or settings.default_rate_basis or DEFAULT_RATE_BASIS
    try:
        validate_rate_basis(rate_basis)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.rental_end <= payload.rental_start:
        raise HTTPException(status_code=400, detail="rental_end must be after rental_start")
    if not payload.lines:
        raise HTTPException(status_code=400, detail="At least one line is required")

    lines: list[RentalContractLine] = []
    assets: dict[int, RentalAsset] = {}
    all_conflicts: list[str] = []

    for item in payload.lines:
        asset = (
            db.query(RentalAsset)
            .filter(RentalAsset.id == item.rental_asset_id, RentalAsset.company_id == company.id)
            .first()
        )
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset {item.rental_asset_id} not found")
        if asset.status == "retired":
            raise HTTPException(status_code=400, detail=f"Asset {asset.asset_code} is retired")

        line_basis = item.rate_basis or rate_basis
        try:
            validate_rate_basis(line_basis)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        rate = unit_rate_for_basis(asset, line_basis)
        if rate is None:
            raise HTTPException(status_code=400, detail=f"No rate for asset {asset.asset_code}")

        days, unit_r, sub, gst, total = compute_line_pricing(
            asset, item.quantity, line_basis, payload.rental_start, payload.rental_end
        )
        line = RentalContractLine(
            rental_asset_id=asset.id,
            quantity=item.quantity,
            rate_basis=line_basis,
            unit_rate=unit_r,
            line_days=days,
            line_subtotal=sub,
            gst_rate=gst,
            line_total=total,
        )
        lines.append(line)
        assets[asset.id] = asset

        conflicts = check_availability(
            db,
            company.id,
            asset.id,
            item.quantity,
            payload.rental_start,
            payload.rental_end,
            exclude_contract_id=contract.id if contract.id else None,
            allow_overbook=bool(settings.allow_overbook),
        )
        all_conflicts.extend(conflicts)

    return lines, assets, all_conflicts


@router.get("/settings", response_model=RentalSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    return _settings_response(_get_settings(db, company))


@router.put("/settings", response_model=RentalSettingsResponse)
def update_settings(
    payload: RentalSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.manage_settings")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    data = payload.model_dump(exclude_unset=True)
    if "auto_invoice_mode" in data and data["auto_invoice_mode"] not in ("draft", "issue"):
        raise HTTPException(status_code=400, detail="auto_invoice_mode must be draft or issue")
    for key, value in data.items():
        setattr(settings, key, value)
    log_activity(
        db,
        "rental_settings_updated",
        user_id=user.id,
        details={"company_id": company.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(settings)
    return _settings_response(settings)


@router.get("/assets", response_model=list[RentalAssetResponse])
def list_assets(
    status: str | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    q = db.query(RentalAsset).filter(RentalAsset.company_id == company.id)
    if status:
        q = q.filter(RentalAsset.status == status)
    if category:
        q = q.filter(RentalAsset.category == category)
    assets = q.order_by(RentalAsset.sort_order, RentalAsset.name).all()
    return [_asset_response(a) for a in assets]


@router.post("/assets", response_model=RentalAssetResponse)
def create_asset(
    payload: RentalAssetCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.manage_assets")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    if not any([payload.rate_daily, payload.rate_weekly, payload.rate_monthly]):
        raise HTTPException(status_code=400, detail="At least one rate is required")

    exists = (
        db.query(RentalAsset.id)
        .filter(RentalAsset.company_id == company.id, RentalAsset.asset_code == payload.asset_code)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Asset code already exists")

    asset = RentalAsset(
        company_id=company.id,
        asset_code=payload.asset_code,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        product_id=payload.product_id,
        quantity_available=payload.quantity_available,
        rate_daily=payload.rate_daily,
        rate_weekly=payload.rate_weekly,
        rate_monthly=payload.rate_monthly,
        gst_rate=payload.gst_rate,
        deposit_amount=payload.deposit_amount,
        location_notes=payload.location_notes,
        sort_order=payload.sort_order,
        status="active",
    )
    db.add(asset)
    db.flush()
    log_activity(
        db,
        "rental_asset_created",
        user_id=user.id,
        details={"asset_id": asset.id, "asset_code": asset.asset_code},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(asset)
    return _asset_response(asset)


@router.get("/assets/{asset_id}", response_model=RentalAssetResponse)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    asset = (
        db.query(RentalAsset)
        .filter(RentalAsset.id == asset_id, RentalAsset.company_id == company.id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _asset_response(asset)


@router.put("/assets/{asset_id}", response_model=RentalAssetResponse)
def update_asset(
    asset_id: int,
    payload: RentalAssetUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.manage_assets")),
):
    company = get_current_company(db, user)
    asset = (
        db.query(RentalAsset)
        .filter(RentalAsset.id == asset_id, RentalAsset.company_id == company.id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if payload.status and payload.status not in ASSET_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid asset status")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    log_activity(
        db,
        "rental_asset_updated",
        user_id=user.id,
        details={"asset_id": asset.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(asset)
    return _asset_response(asset)


@router.get("/assets/{asset_id}/bookings", response_model=list[ContractListItem])
def asset_bookings(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    lines = (
        db.query(RentalContract)
        .join(RentalContractLine, RentalContractLine.contract_id == RentalContract.id)
        .options(joinedload(RentalContract.contact))
        .filter(
            RentalContract.company_id == company.id,
            RentalContractLine.rental_asset_id == asset_id,
            RentalContract.status.notin_(("draft", "cancelled")),
        )
        .order_by(RentalContract.rental_start.desc())
        .all()
    )
    return [_contract_list_item(c) for c in lines]


@router.get("/dashboard", response_model=RentalDashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    send_rental_reminders(db, company, settings)
    db.commit()

    now = _utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_end = now + timedelta(days=7)

    contracts = (
        db.query(RentalContract)
        .options(joinedload(RentalContract.contact), joinedload(RentalContract.lines))
        .filter(RentalContract.company_id == company.id)
        .all()
    )
    assets = db.query(RentalAsset).filter(
        RentalAsset.company_id == company.id, RentalAsset.status == "active"
    ).all()
    total_units = sum(int(a.quantity_available or 0) for a in assets)

    active = [c for c in contracts if c.status in ("delivered", "on_rent", "return_scheduled")]
    units_on_rent = 0
    for c in active:
        for ln in c.lines or []:
            units_on_rent += int(ln.quantity or 0)

    returns_due = [
        c for c in contracts
        if c.status in ("on_rent", "delivered", "return_scheduled") and c.rental_end <= week_end
    ]
    overdue = [
        c for c in contracts
        if c.status in ("on_rent", "delivered", "return_scheduled") and c.rental_end < now
    ]
    awaiting_deposit = [
        c for c in contracts
        if c.status in ("confirmed", "draft")
        and _float(c.deposit_required) > 0
        and _float(c.deposit_received) < _float(c.deposit_required)
    ]
    closed_mtd = [
        c for c in contracts
        if c.status == "closed" and c.updated_at and c.updated_at >= month_start
    ]
    deposits_held = sum(_float(deposit_held(c)) for c in contracts if c.status not in ("closed", "cancelled"))
    revenue_mtd = sum(_float(c.grand_total) for c in closed_mtd)
    utilization = (units_on_rent / total_units * 100) if total_units > 0 else 0.0

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    deliveries_today = [
        c for c in contracts
        if c.delivery_scheduled_at and today_start <= c.delivery_scheduled_at < today_end
    ]

    recently_closed = sorted(
        [c for c in contracts if c.status == "closed"],
        key=lambda c: c.updated_at or _utcnow(),
        reverse=True,
    )[:10]

    return RentalDashboardResponse(
        active_contracts=len(active),
        units_on_rent=units_on_rent,
        returns_due_7d=len(returns_due),
        overdue_returns=len(overdue),
        deposits_held=round(deposits_held, 2),
        revenue_mtd=round(revenue_mtd, 2),
        utilization_pct=round(utilization, 1),
        deliveries_today=[_contract_list_item(c) for c in deliveries_today[:20]],
        returns_due=[_contract_list_item(c) for c in sorted(returns_due, key=lambda x: x.rental_end)[:20]],
        overdue=[_contract_list_item(c) for c in overdue[:20]],
        awaiting_deposit=[_contract_list_item(c) for c in awaiting_deposit[:20]],
        recently_closed=[_contract_list_item(c) for c in recently_closed],
    )


@router.get("/calendar", response_model=CalendarResponse)
def calendar(
    week_start: datetime | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))

    start = week_start or _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = start - timedelta(days=start.weekday())
    end = start + timedelta(days=7)

    lines = (
        db.query(RentalContractLine)
        .join(RentalContract, RentalContractLine.contract_id == RentalContract.id)
        .options(
            joinedload(RentalContractLine.rental_asset),
            joinedload(RentalContractLine.contract).joinedload(RentalContract.contact),
        )
        .filter(
            RentalContract.company_id == company.id,
            RentalContract.status.notin_(("draft", "cancelled", "closed")),
            RentalContract.rental_end >= start,
            RentalContract.rental_start <= end,
        )
        .all()
    )

    events: list[CalendarEvent] = []
    for line in lines:
        contract = line.contract
        asset = line.rental_asset
        if not contract or not asset:
            continue
        events.append(
            CalendarEvent(
                contract_id=contract.id,
                contract_number=contract.contract_number,
                rental_asset_id=asset.id,
                asset_name=asset.name,
                asset_code=asset.asset_code,
                contact_name=contract.contact.name if contract.contact else None,
                quantity=int(line.quantity or 1),
                rental_start=contract.rental_start,
                rental_end=contract.rental_end,
                status=contract.status,
            )
        )

    return CalendarResponse(events=events, week_start=start, week_end=end)


@router.get("/contracts", response_model=ContractListResponse)
def list_contracts(
    status: str | None = Query(None),
    contact_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    q = (
        db.query(RentalContract)
        .options(joinedload(RentalContract.contact))
        .filter(RentalContract.company_id == company.id)
    )
    if status:
        q = q.filter(RentalContract.status == status)
    if contact_id:
        q = q.filter(RentalContract.contact_id == contact_id)
    total = q.count()
    contracts = q.order_by(RentalContract.created_at.desc()).offset(skip).limit(limit).all()
    return ContractListResponse(items=[_contract_list_item(c) for c in contracts], total=total)


@router.post("/contracts", response_model=ContractResponse)
def create_contract(
    payload: ContractCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.create")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    contact = (
        db.query(Contact)
        .filter(Contact.id == payload.contact_id, Contact.company_id == company.id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    rate_basis = payload.rate_basis or settings.default_rate_basis or DEFAULT_RATE_BASIS
    prefix = settings.contract_prefix or DEFAULT_CONTRACT_PREFIX
    contract = RentalContract(
        company_id=company.id,
        contract_number=generate_contract_number(db, company.id, prefix),
        contact_id=contact.id,
        status="draft",
        rate_basis=rate_basis,
        rental_start=payload.rental_start,
        rental_end=payload.rental_end,
        delivery_address=payload.delivery_address or ", ".join(
            p for p in [contact.address_line1, contact.city, contact.state] if p
        ),
        delivery_contact_name=payload.delivery_contact_name or contact.name,
        delivery_contact_phone=payload.delivery_contact_phone or contact.phone,
        notes=payload.notes,
        created_by_id=user.id,
    )
    db.add(contract)
    db.flush()

    lines, assets, conflicts = _build_contract_lines(db, company, contract, payload, settings)
    contract.lines = lines
    subtotal, grand_total, deposit_required = compute_contract_totals(lines, settings, assets)
    contract.subtotal = subtotal
    contract.grand_total = grand_total
    contract.deposit_required = deposit_required

    log_activity(
        db,
        "rental_contract_created",
        user_id=user.id,
        details={"contract_id": contract.id, "contract_number": contract.contract_number},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _contract_response(_load_contract(db, company.id, contract.id), conflicts)


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    return _contract_response(_load_contract(db, company.id, contract_id))


@router.get("/contracts/{contract_id}/availability", response_model=AvailabilityCheckResponse)
def check_contract_availability(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    contract = _load_contract(db, company.id, contract_id)
    conflicts: list[str] = []
    for line in contract.lines or []:
        conflicts.extend(
            check_availability(
                db,
                company.id,
                line.rental_asset_id,
                int(line.quantity or 1),
                contract.rental_start,
                contract.rental_end,
                exclude_contract_id=contract.id,
                allow_overbook=bool(settings.allow_overbook),
            )
        )
    return AvailabilityCheckResponse(available=len(conflicts) == 0, conflicts=conflicts)


@router.post("/contracts/{contract_id}/confirm", response_model=ContractResponse)
def confirm_contract(
    contract_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.confirm")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    contract = _load_contract(db, company.id, contract_id)

    if contract.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft contracts can be confirmed")

    conflicts: list[str] = []
    for line in contract.lines or []:
        conflicts.extend(
            check_availability(
                db,
                company.id,
                line.rental_asset_id,
                int(line.quantity or 1),
                contract.rental_start,
                contract.rental_end,
                exclude_contract_id=contract.id,
                allow_overbook=bool(settings.allow_overbook),
            )
        )
    if conflicts and not settings.allow_overbook:
        raise HTTPException(status_code=400, detail={"message": "Availability conflict", "conflicts": conflicts})

    contract.status = "confirmed"
    log_activity(
        db,
        "rental_contract_confirmed",
        user_id=user.id,
        details={"contract_id": contract.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _contract_response(_load_contract(db, company.id, contract_id))


@router.post("/contracts/{contract_id}/cancel", response_model=ContractResponse)
def cancel_contract(
    contract_id: int,
    payload: ContractCancelRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.cancel")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    contract = _load_contract(db, company.id, contract_id)

    if contract.status in ("closed", "cancelled"):
        raise HTTPException(status_code=400, detail="Contract already ended")

    contract.status = "cancelled"
    contract.cancellation_reason = payload.cancellation_reason
    log_activity(
        db,
        "rental_contract_cancelled",
        user_id=user.id,
        details={"contract_id": contract.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _contract_response(_load_contract(db, company.id, contract_id))


@router.post("/contracts/{contract_id}/dispatch", response_model=ContractResponse)
def dispatch_contract(
    contract_id: int,
    payload: ContractDispatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.dispatch")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    contract = _load_contract(db, company.id, contract_id)

    if contract.status not in ("confirmed",):
        raise HTTPException(status_code=400, detail="Contract must be confirmed before dispatch")
    if not contract.delivery_address:
        raise HTTPException(status_code=400, detail="Delivery address is required")
    if settings.require_deposit_before_delivery and _float(contract.deposit_received) < _float(contract.deposit_required):
        raise HTTPException(status_code=400, detail="Deposit must be received before delivery")

    now = _utcnow()
    contract.delivery_scheduled_at = payload.delivery_scheduled_at or now
    contract.delivery_completed_at = now
    contract.status = "delivered"
    if contract.rental_start <= now:
        contract.status = "on_rent"

    log_activity(
        db,
        "rental_delivered",
        user_id=user.id,
        details={"contract_id": contract.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _contract_response(_load_contract(db, company.id, contract_id))


@router.post("/contracts/{contract_id}/schedule-return", response_model=ContractResponse)
def schedule_return(
    contract_id: int,
    payload: ContractScheduleReturnRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.process_return")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    contract = _load_contract(db, company.id, contract_id)

    if contract.status not in ("on_rent", "delivered"):
        raise HTTPException(status_code=400, detail="Contract must be on rent to schedule return")

    contract.return_scheduled_at = payload.return_scheduled_at
    contract.status = "return_scheduled"
    log_activity(
        db,
        "rental_return_scheduled",
        user_id=user.id,
        details={"contract_id": contract.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _contract_response(_load_contract(db, company.id, contract_id))


@router.post("/contracts/{contract_id}/return", response_model=ContractResponse)
def complete_return(
    contract_id: int,
    payload: ContractReturnRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.process_return")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    contract = _load_contract(db, company.id, contract_id)

    if contract.status not in ("on_rent", "delivered", "return_scheduled"):
        raise HTTPException(status_code=400, detail="Contract is not eligible for return")

    actual = payload.actual_return_at or _utcnow()
    contract.actual_return_at = actual
    contract.return_completed_at = actual

    line_map = {ln.id: ln for ln in contract.lines or []}
    damage_total = 0.0
    for item in payload.lines:
        try:
            validate_return_condition(item.return_condition)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        line = line_map.get(item.line_id)
        if not line:
            raise HTTPException(status_code=404, detail=f"Line {item.line_id} not found")
        line.return_condition = item.return_condition
        line.damage_notes = item.damage_notes
        if item.damage_charge:
            line.damage_charge = item.damage_charge
            damage_total += item.damage_charge

    contract.damage_charge_total = damage_total
    contract.late_fee_total = _float(compute_late_fee(contract, settings, actual))
    contract.status = "returned"

    log_activity(
        db,
        "rental_returned",
        user_id=user.id,
        details={"contract_id": contract.id, "late_fee": contract.late_fee_total},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _contract_response(_load_contract(db, company.id, contract_id))


@router.post("/contracts/{contract_id}/close", response_model=ContractResponse)
def close_contract(
    contract_id: int,
    payload: ContractCloseRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.process_return")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    contract = _load_contract(db, company.id, contract_id)

    if contract.status != "returned":
        raise HTTPException(status_code=400, detail="Contract must be returned before close")
    for line in contract.lines or []:
        if not line.return_condition:
            raise HTTPException(status_code=400, detail="All lines must have return condition")

    held = deposit_held(contract)
    deduct_total = _float(contract.damage_charge_total) + _float(contract.late_fee_total)
    if deduct_total > 0 and held > 0:
        deduct_amt = min(held, deduct_total)
        dep = RentalDeposit(
            contract_id=contract.id,
            type="deduction",
            amount=deduct_amt,
            payment_method="other",
            notes="Damage/late fee deduction on close",
            recorded_by_id=user.id,
            recorded_at=_utcnow(),
        )
        db.add(dep)

    sync_deposit_totals(contract)
    held = deposit_held(contract)
    refund_amt = payload.refund_amount if payload.refund_amount is not None else _float(held)
    if refund_amt > 0:
        if refund_amt > _float(held):
            raise HTTPException(status_code=400, detail="Refund exceeds held deposit")
        dep = RentalDeposit(
            contract_id=contract.id,
            type="refund",
            amount=refund_amt,
            payment_method="bank",
            notes="Deposit refund on contract close",
            recorded_by_id=user.id,
            recorded_at=_utcnow(),
        )
        db.add(dep)

    sync_deposit_totals(contract)
    contract.status = "closed"
    log_activity(
        db,
        "rental_closed",
        user_id=user.id,
        details={"contract_id": contract.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _contract_response(_load_contract(db, company.id, contract_id))


@router.post("/contracts/{contract_id}/deposits", response_model=DepositRecordResponse)
def record_deposit(
    contract_id: int,
    payload: DepositRecordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.manage_deposits")),
):
    company = get_current_company(db, user)
    _require_enabled(_get_settings(db, company))
    contract = _load_contract(db, company.id, contract_id)

    try:
        validate_deposit_type(payload.type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.type == "refund" and payload.amount > _float(deposit_held(contract)):
        raise HTTPException(status_code=400, detail="Refund exceeds held deposit")

    dep = RentalDeposit(
        contract_id=contract.id,
        type=payload.type,
        amount=payload.amount,
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
        recorded_by_id=user.id,
        recorded_at=_utcnow(),
    )
    db.add(dep)
    db.flush()
    sync_deposit_totals(contract)
    log_activity(
        db,
        "rental_deposit_recorded",
        user_id=user.id,
        details={"contract_id": contract.id, "type": payload.type, "amount": payload.amount},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return DepositRecordResponse(
        id=dep.id,
        type=dep.type,
        amount=_float(dep.amount),
        payment_method=dep.payment_method,
        reference=dep.reference,
        notes=dep.notes,
        recorded_at=dep.recorded_at,
    )


@router.get("/contracts/{contract_id}/deposits", response_model=list[DepositRecordResponse])
def list_deposits(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.view")),
):
    company = get_current_company(db, user)
    contract = _load_contract(db, company.id, contract_id)
    return _contract_response(contract).deposits


@router.post("/contracts/{contract_id}/generate-invoice", response_model=RentalInvoiceLink)
def generate_invoice(
    contract_id: int,
    request: Request,
    invoice_type: str = Query("rental"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rental.manage_deposits")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    contract = _load_contract(db, company.id, contract_id)

    extra_lines = None
    if invoice_type == "damage" and _float(contract.damage_charge_total) > 0:
        extra_lines = [{
            "name": f"Damage charges — {contract.contract_number}",
            "line_subtotal": _float(contract.damage_charge_total),
            "line_total": _float(contract.damage_charge_total) * 1.18,
            "gst_rate": 18,
        }]
    elif invoice_type == "late_fee" and _float(contract.late_fee_total) > 0:
        extra_lines = [{
            "name": f"Late return fee — {contract.contract_number}",
            "line_subtotal": _float(contract.late_fee_total),
            "line_total": _float(contract.late_fee_total) * 1.18,
            "gst_rate": 18,
        }]
    elif invoice_type != "rental":
        raise HTTPException(status_code=400, detail="Invalid invoice type")

    inv = create_contract_invoice(db, company, user, contract, settings, invoice_type, extra_lines)
    log_activity(
        db,
        "rental_invoice_generated",
        user_id=user.id,
        details={"contract_id": contract.id, "invoice_id": inv.id, "type": invoice_type},
        ip_address=get_client_ip(request),
    )
    db.commit()
    link = contract.rental_invoices[-1] if contract.rental_invoices else None
    return RentalInvoiceLink(
        id=link.id if link else 0,
        invoice_id=inv.id,
        invoice_number=inv.invoice_number,
        invoice_status=inv.status,
        invoice_type=invoice_type,
        grand_total=_float(inv.grand_total),
        generated_at=inv.created_at,
    )
