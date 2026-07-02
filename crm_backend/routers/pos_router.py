"""POS — point of sale API."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from auth_utils import get_client_ip, get_db, require_permission
from company_branding import build_company_branding
from invoice_config import DEFAULT_BANK_INSTRUCTIONS, DEFAULT_BILLING_NOTES, DEFAULT_PAYMENT_TERMS
from models import (
    Company,
    Contact,
    Invoice,
    InvoiceLineItem,
    InvoicePayment,
    PosBill,
    PosBillItem,
    PosCart,
    PosCartItem,
    PosPayment,
    PosRegister,
    PosReturn,
    PosSession,
    PosSettings,
    Product,
    User,
)
from pos_config import (
    MAX_LINE_QTY,
    PAYMENT_METHODS,
    product_unit_price,
)
from pos_schemas import (
    PosBillListItem,
    PosBillListResponse,
    PosBillResponse,
    PosBillItemResponse,
    PosBillPaymentResponse,
    PosBillVoidRequest,
    PosCartAddRequest,
    PosCartCustomerRequest,
    PosCartHoldRequest,
    PosCartItemResponse,
    PosCartResponse,
    PosCartUpdateRequest,
    PosCatalogItemResponse,
    PosCatalogResponse,
    PosCatalogUpdateRequest,
    PosCheckoutRequest,
    PosCheckoutResponse,
    PosDashboardResponse,
    PosProductTerminal,
    PosReceiptResponse,
    PosRegisterCreateRequest,
    PosRegisterResponse,
    PosReturnListItem,
    PosReturnListResponse,
    PosReturnRequest,
    PosSessionCloseRequest,
    PosSessionOpenRequest,
    PosSessionResponse,
    PosSettingsResponse,
    PosSettingsUpdateRequest,
    PosZReportResponse,
)
from routers.inventory_router import _apply_movement
from routers.invoices_router import _sync_balances
from services.document_number_service import generate_invoice_number

router = APIRouter(prefix="/pos", tags=["pos"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)


def _get_company(db: Session) -> Company:
    company = db.query(Company).first()
    if not company:
        raise HTTPException(status_code=400, detail="Company must be configured")
    return company


def _get_settings(db: Session, company: Company) -> PosSettings:
    settings = db.query(PosSettings).filter(PosSettings.company_id == company.id).first()
    if settings:
        return settings
    settings = PosSettings(company_id=company.id, is_enabled=True)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _require_pos_enabled(settings: PosSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="POS is not enabled")


def _settings_response(settings: PosSettings) -> PosSettingsResponse:
    return PosSettingsResponse(
        is_enabled=settings.is_enabled,
        default_register_id=settings.default_register_id,
        bill_number_prefix=settings.bill_number_prefix,
        auto_create_invoice=settings.auto_create_invoice,
        inventory_deduct_on_sale=settings.inventory_deduct_on_sale,
        allow_negative_stock=settings.allow_negative_stock,
        receipt_header=settings.receipt_header,
        receipt_footer=settings.receipt_footer,
        require_customer_phone=settings.require_customer_phone,
        max_line_discount_pct=_float(settings.max_line_discount_pct),
        return_window_days=settings.return_window_days,
    )


def _get_session(db: Session, session_id: int, company_id: int) -> PosSession:
    session = (
        db.query(PosSession)
        .options(joinedload(PosSession.register), joinedload(PosSession.opened_by))
        .filter(PosSession.id == session_id, PosSession.company_id == company_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _require_open_session(session: PosSession) -> None:
    if session.status != "open":
        raise HTTPException(status_code=400, detail="Session is closed")


def _session_dep(
    x_pos_session_id: int | None = Header(default=None, alias="X-Pos-Session-Id"),
    user: User = Depends(require_permission("pos.bill")),
    db: Session = Depends(get_db),
) -> PosSession:
    if not x_pos_session_id:
        raise HTTPException(status_code=400, detail="X-Pos-Session-Id header required")
    session = _get_session(db, x_pos_session_id, user.company_id)
    _require_open_session(session)
    return session


def _product_in_stock(product: Product, settings: PosSettings) -> bool:
    if not product.inventory_tracked:
        return True
    if settings.allow_negative_stock:
        return True
    return _float(product.on_hand_quantity) > 0


def _line_total(qty: float, unit_price: float, discount: float, gst_rate: float) -> tuple[float, float]:
    sub = qty * unit_price
    after_disc = max(sub - discount, 0)
    tax = after_disc * (gst_rate / 100)
    return after_disc + tax, tax


def _recalc_cart(cart: PosCart) -> None:
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    tax_total = Decimal("0")
    for item in cart.items:
        qty = _float(item.quantity)
        price = _float(item.unit_price)
        disc = _float(item.discount_amount)
        gst = _float(item.gst_rate)
        line_sub = qty * price
        after = max(line_sub - disc, 0)
        tax = after * (gst / 100)
        lt = after + tax
        item.line_total = Decimal(str(round(lt, 2)))
        subtotal += Decimal(str(line_sub))
        discount_total += Decimal(str(disc))
        tax_total += Decimal(str(tax))
    cart.subtotal = subtotal
    cart.discount_total = discount_total
    cart.tax_total = tax_total
    cart.grand_total = max(subtotal - discount_total, Decimal("0")) + tax_total


def _load_cart(db: Session, cart_id: int) -> PosCart:
    return (
        db.query(PosCart)
        .options(joinedload(PosCart.items).joinedload(PosCartItem.product))
        .filter(PosCart.id == cart_id)
        .first()
    )


def _get_or_create_active_cart(db: Session, session: PosSession, user: User) -> PosCart:
    cart = (
        db.query(PosCart)
        .options(joinedload(PosCart.items).joinedload(PosCartItem.product))
        .filter(PosCart.session_id == session.id, PosCart.status == "active")
        .first()
    )
    if cart:
        return cart
    cart = PosCart(company_id=session.company_id, session_id=session.id, created_by_id=user.id)
    db.add(cart)
    db.flush()
    return cart


def _cart_response(cart: PosCart) -> PosCartResponse:
    items = []
    for item in cart.items:
        product = item.product
        items.append(
            PosCartItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product.name if product else "Product",
                quantity=_float(item.quantity),
                unit_price=_float(item.unit_price),
                discount_amount=_float(item.discount_amount),
                gst_rate=_float(item.gst_rate),
                line_total=_float(item.line_total),
            )
        )
    return PosCartResponse(
        id=cart.id,
        status=cart.status,
        items=items,
        item_count=len(items),
        subtotal=_float(cart.subtotal),
        discount_total=_float(cart.discount_total),
        tax_total=_float(cart.tax_total),
        grand_total=_float(cart.grand_total),
        customer_name=cart.customer_name,
        customer_phone=cart.customer_phone,
        held_label=cart.held_label,
    )


def _generate_bill_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    like = f"{prefix}-{year}-%"
    count = db.query(func.count(PosBill.id)).filter(PosBill.company_id == company_id, PosBill.bill_number.like(like)).scalar()
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _generate_return_number(db: Session, company_id: int) -> str:
    year = _utcnow().year
    prefix = "RET-POS"
    like = f"{prefix}-{year}-%"
    count = db.query(func.count(PosReturn.id)).filter(PosReturn.company_id == company_id, PosReturn.return_number.like(like)).scalar()
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _get_pos_product(db: Session, company_id: int, product_id: int) -> Product:
    product = db.query(Product).filter(Product.company_id == company_id, Product.id == product_id, Product.sell_at_pos.is_(True), Product.status == "active").first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not available at POS")
    return product


def _deduct_stock(db: Session, product: Product, user: User, qty: float, bill_number: str, allow_negative: bool) -> None:
    if not product.inventory_tracked:
        return
    try:
        _apply_movement(
            db,
            product,
            user,
            "sale",
            qty,
            _float(product.unit_valuation),
            _utcnow(),
            reason="sale_dispatch",
            notes=f"POS sale {bill_number}",
            reference_number=bill_number,
            reference_type="pos_bill",
            source_module="pos",
            allow_negative=allow_negative,
        )
    except HTTPException:
        if not allow_negative:
            raise


def _restock(db: Session, product: Product, user: User, qty: float, ref: str) -> None:
    if not product.inventory_tracked:
        return
    _apply_movement(
        db,
        product,
        user,
        "adjustment",
        qty,
        _float(product.unit_valuation),
        _utcnow(),
        adjustment_direction="in",
        reason="customer_return",
        notes=f"POS return {ref}",
        reference_number=ref,
        reference_type="pos_return",
        source_module="pos",
    )


def _create_invoice_for_bill(db: Session, company: Company, user: User, bill: PosBill) -> Invoice | None:
    inv = Invoice(
        company_id=company.id,
        created_by_id=user.id,
        issued_by_id=user.id,
        contact_id=bill.contact_id,
        title=f"POS Bill {bill.bill_number}",
        status="issued",
        invoice_type="standard",
        source_type="pos",
        currency=company.currency or "INR",
        issue_date=bill.completed_at or _utcnow(),
        due_date=bill.completed_at or _utcnow(),
        client_name=bill.customer_name or "Walk-in",
        client_phone=bill.customer_phone,
        client_gstin=bill.customer_gstin,
        subtotal=bill.subtotal,
        line_discount_total=bill.discount_total,
        total_tax=bill.tax_total,
        grand_total=bill.grand_total,
        outstanding_amount=bill.grand_total,
        amount_paid=Decimal("0"),
        requires_review=0,
        internal_notes=f"Generated from POS bill {bill.bill_number}",
        payment_terms=DEFAULT_PAYMENT_TERMS,
        bank_instructions=DEFAULT_BANK_INSTRUCTIONS,
        billing_notes=DEFAULT_BILLING_NOTES,
    )
    db.add(inv)
    db.flush()
    inv.invoice_number = generate_invoice_number(db, company)
    inv.issued_at = _utcnow()
    inv.share_token = secrets.token_urlsafe(32)
    for idx, item in enumerate(bill.items):
        qty = _float(item.quantity)
        price = _float(item.unit_price)
        disc = _float(item.discount_amount)
        gst = _float(item.gst_rate)
        ls = qty * price
        after = max(ls - disc, 0)
        lt = after + after * (gst / 100)
        inv.line_items.append(
            InvoiceLineItem(
                product_id=item.product_id,
                sort_order=idx,
                item_name=item.product_name_snapshot,
                quantity=item.quantity,
                unit="Nos",
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                tax_rate=item.gst_rate,
                line_subtotal=Decimal(str(ls)),
                line_total=Decimal(str(lt)),
            )
        )
    payment = bill.payments[0] if bill.payments else None
    if payment:
        inv.payments.append(
            InvoicePayment(
                amount=payment.amount,
                payment_date=bill.completed_at or _utcnow(),
                payment_method=payment.method,
                reference=payment.reference,
                note=f"POS {bill.bill_number}",
                recorded_by_id=user.id,
            )
        )
        _sync_balances(inv)
    return inv


def _bill_list_item(bill: PosBill) -> PosBillListItem:
    pay_method = bill.payments[0].method if bill.payments else "—"
    name = bill.customer_name or "Walk-in"
    return PosBillListItem(
        id=bill.id,
        bill_number=bill.bill_number,
        customer_name=name,
        item_count=len(bill.items),
        grand_total=_float(bill.grand_total),
        status=bill.status,
        payment_method=pay_method,
        cashier_name=bill.cashier.name if bill.cashier else "—",
        completed_at=bill.completed_at,
    )


def _bill_response(bill: PosBill) -> PosBillResponse:
    return PosBillResponse(
        id=bill.id,
        bill_number=bill.bill_number,
        status=bill.status,
        subtotal=_float(bill.subtotal),
        discount_total=_float(bill.discount_total),
        tax_total=_float(bill.tax_total),
        grand_total=_float(bill.grand_total),
        customer_name=bill.customer_name,
        customer_phone=bill.customer_phone,
        customer_gstin=bill.customer_gstin,
        contact_id=bill.contact_id,
        invoice_id=bill.invoice_id,
        session_id=bill.session_id,
        register_name=bill.register.name if bill.register else "",
        cashier_name=bill.cashier.name if bill.cashier else "",
        completed_at=bill.completed_at,
        items=[
            PosBillItemResponse(
                id=i.id,
                product_id=i.product_id,
                product_name_snapshot=i.product_name_snapshot,
                quantity=_float(i.quantity),
                unit_price=_float(i.unit_price),
                discount_amount=_float(i.discount_amount),
                gst_rate=_float(i.gst_rate),
                line_total=_float(i.line_total),
            )
            for i in bill.items
        ],
        payments=[
            PosBillPaymentResponse(
                id=p.id,
                amount=_float(p.amount),
                method=p.method,
                reference=p.reference,
                status=p.status,
            )
            for p in bill.payments
        ],
    )


def _get_bill(db: Session, bill_id: int, company_id: int) -> PosBill:
    bill = (
        db.query(PosBill)
        .options(
            joinedload(PosBill.items),
            joinedload(PosBill.payments),
            joinedload(PosBill.register),
            joinedload(PosBill.cashier),
        )
        .filter(PosBill.id == bill_id, PosBill.company_id == company_id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


def _session_response(session: PosSession) -> PosSessionResponse:
    return PosSessionResponse(
        id=session.id,
        register_id=session.register_id,
        register_name=session.register.name if session.register else "",
        status=session.status,
        opening_float=_float(session.opening_float),
        closing_cash_counted=_float(session.closing_cash_counted) if session.closing_cash_counted is not None else None,
        expected_cash=_float(session.expected_cash) if session.expected_cash is not None else None,
        cash_variance=_float(session.cash_variance) if session.cash_variance is not None else None,
        opened_by_name=session.opened_by.name if session.opened_by else "",
        opened_at=session.opened_at,
        closed_at=session.closed_at,
    )


def _receipt_html(company: Company, settings: PosSettings, bill: PosBill) -> str:
    sys_settings = db_branding = None
    branding = build_company_branding(company, None)
    lines = "".join(
        f"<tr><td>{i.product_name_snapshot}</td><td>{_float(i.quantity)}</td><td>{_float(i.unit_price):.2f}</td><td>{_float(i.line_total):.2f}</td></tr>"
        for i in bill.items
    )
    pay = bill.payments[0] if bill.payments else None
    header = settings.receipt_header or branding.display_name
    footer = settings.receipt_footer or "Thank you for your purchase!"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{bill.bill_number}</title>
    <style>body{{font-family:monospace;max-width:300px;margin:0 auto;font-size:12px}}
    table{{width:100%;border-collapse:collapse}}td{{padding:2px 0}}</style></head><body>
    <h3 style="text-align:center">{header}</h3>
    <p style="text-align:center">{branding.gstin or ''}<br>{branding.phone or ''}</p>
    <p>Bill: <strong>{bill.bill_number}</strong><br>{bill.completed_at.strftime('%d/%m/%Y %H:%M') if bill.completed_at else ''}</p>
    <table><tr><th>Item</th><th>Qty</th><th>Rate</th><th>Amt</th></tr>{lines}</table>
    <p>Subtotal: ₹{_float(bill.subtotal):.2f}<br>GST: ₹{_float(bill.tax_total):.2f}<br><strong>Total: ₹{_float(bill.grand_total):.2f}</strong></p>
    <p>Payment: {pay.method.upper() if pay else '—'}</p>
    <p style="text-align:center">{footer}</p></body></html>"""


# --- Dashboard & settings ---

@router.get("/dashboard", response_model=PosDashboardResponse)
def dashboard(user: User = Depends(require_permission("pos.view")), db: Session = Depends(get_db)):
    company = _get_company(db)
    today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    bills = (
        db.query(PosBill)
        .options(joinedload(PosBill.items), joinedload(PosBill.payments), joinedload(PosBill.cashier))
        .filter(PosBill.company_id == company.id, PosBill.status == "completed", PosBill.completed_at >= today_start)
        .order_by(PosBill.completed_at.desc())
        .all()
    )
    mix: dict[str, float] = {}
    for b in bills:
        for p in b.payments:
            mix[p.method] = mix.get(p.method, 0) + _float(p.amount)
    open_sessions = db.query(func.count(PosSession.id)).filter(PosSession.company_id == company.id, PosSession.status == "open").scalar()
    return PosDashboardResponse(
        sales_today=sum(_float(b.grand_total) for b in bills),
        bills_today=len(bills),
        open_sessions=int(open_sessions or 0),
        payment_mix=mix,
        recent_bills=[_bill_list_item(b) for b in bills[:10]],
    )


@router.get("/settings", response_model=PosSettingsResponse)
def get_settings(user: User = Depends(require_permission("pos.view")), db: Session = Depends(get_db)):
    company = _get_company(db)
    return _settings_response(_get_settings(db, company))


@router.put("/settings", response_model=PosSettingsResponse)
def update_settings(
    data: PosSettingsUpdateRequest,
    user: User = Depends(require_permission("pos.manage_settings")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return _settings_response(settings)


@router.get("/registers", response_model=list[PosRegisterResponse])
def list_registers(user: User = Depends(require_permission("pos.view")), db: Session = Depends(get_db)):
    company = _get_company(db)
    registers = db.query(PosRegister).filter(PosRegister.company_id == company.id).order_by(PosRegister.name).all()
    open_ids = {
        r[0]
        for r in db.query(PosSession.register_id)
        .filter(PosSession.company_id == company.id, PosSession.status == "open")
        .all()
    }
    return [
        PosRegisterResponse(
            id=r.id,
            name=r.name,
            code=r.code,
            is_active=r.is_active,
            default_payment_method=r.default_payment_method,
            opening_float_default=_float(r.opening_float_default),
            has_open_session=r.id in open_ids,
        )
        for r in registers
    ]


@router.post("/registers", response_model=PosRegisterResponse)
def create_register(
    data: PosRegisterCreateRequest,
    user: User = Depends(require_permission("pos.manage_settings")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    existing = db.query(PosRegister).filter(PosRegister.company_id == company.id, PosRegister.code == data.code.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Register code already exists")
    reg = PosRegister(
        company_id=company.id,
        name=data.name.strip(),
        code=data.code.strip().upper(),
        default_payment_method=data.default_payment_method,
        opening_float_default=Decimal(str(data.opening_float_default)),
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    settings = _get_settings(db, company)
    if not settings.default_register_id:
        settings.default_register_id = reg.id
        db.commit()
    return PosRegisterResponse(
        id=reg.id,
        name=reg.name,
        code=reg.code,
        is_active=reg.is_active,
        default_payment_method=reg.default_payment_method,
        opening_float_default=_float(reg.opening_float_default),
        has_open_session=False,
    )


# --- Sessions ---

@router.post("/sessions/open", response_model=PosSessionResponse)
def open_session(
    data: PosSessionOpenRequest,
    user: User = Depends(require_permission("pos.bill")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_pos_enabled(settings)
    reg = db.query(PosRegister).filter(PosRegister.id == data.register_id, PosRegister.company_id == company.id, PosRegister.is_active.is_(True)).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Register not found")
    existing = db.query(PosSession).filter(PosSession.register_id == reg.id, PosSession.status == "open").first()
    if existing:
        raise HTTPException(status_code=400, detail="Register already has an open session")
    session = PosSession(
        company_id=company.id,
        register_id=reg.id,
        opened_by_id=user.id,
        opening_float=Decimal(str(data.opening_float)),
    )
    db.add(session)
    db.flush()
    db.add(PosCart(company_id=company.id, session_id=session.id, created_by_id=user.id))
    db.commit()
    session = _get_session(db, session.id, company.id)
    return _session_response(session)


@router.post("/sessions/{session_id}/close", response_model=PosZReportResponse)
def close_session(
    session_id: int,
    data: PosSessionCloseRequest,
    request: Request,
    user: User = Depends(require_permission("pos.manage_sessions")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    session = _get_session(db, session_id, company.id)
    if session.status != "open":
        raise HTTPException(status_code=400, detail="Session already closed")
    bills = db.query(PosBill).options(joinedload(PosBill.payments)).filter(PosBill.session_id == session.id, PosBill.status == "completed").all()
    cash_sales = sum(_float(p.amount) for b in bills for p in b.payments if p.method == "cash")
    refunds = (
        db.query(PosReturn)
        .join(PosBill, PosBill.id == PosReturn.bill_id)
        .filter(PosBill.session_id == session.id)
        .all()
    )
    cash_refunds = sum(_float(r.refund_amount) for r in refunds if r.refund_method == "cash")
    expected = _float(session.opening_float) + cash_sales - cash_refunds
    counted = float(data.closing_cash_counted)
    session.closing_cash_counted = Decimal(str(counted))
    session.expected_cash = Decimal(str(expected))
    session.cash_variance = Decimal(str(counted - expected))
    session.status = "closed"
    session.closed_at = _utcnow()
    session.closed_by_id = user.id
    session.notes = data.notes
    db.commit()
    mix: dict[str, float] = {}
    for b in bills:
        for p in b.payments:
            mix[p.method] = mix.get(p.method, 0) + _float(p.amount)
    void_count = db.query(func.count(PosBill.id)).filter(PosBill.session_id == session.id, PosBill.status == "voided").scalar()
    return PosZReportResponse(
        session=_session_response(_get_session(db, session.id, company.id)),
        bill_count=len(bills),
        gross_sales=sum(_float(b.subtotal) for b in bills),
        discount_total=sum(_float(b.discount_total) for b in bills),
        net_sales=sum(_float(b.grand_total) for b in bills),
        payment_breakdown=mix,
        cash_opening=_float(session.opening_float),
        cash_sales=cash_sales,
        cash_refunds=cash_refunds,
        cash_expected=expected,
        cash_counted=counted,
        cash_variance=counted - expected,
        void_count=int(void_count or 0),
        return_count=len(refunds),
    )


@router.get("/sessions", response_model=list[PosSessionResponse])
def list_sessions(
    status: str | None = None,
    user: User = Depends(require_permission("pos.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    q = db.query(PosSession).options(joinedload(PosSession.register), joinedload(PosSession.opened_by)).filter(PosSession.company_id == company.id)
    if status:
        q = q.filter(PosSession.status == status)
    sessions = q.order_by(PosSession.opened_at.desc()).limit(50).all()
    return [_session_response(s) for s in sessions]


@router.get("/sessions/{session_id}/z-report", response_model=PosZReportResponse)
def get_z_report(session_id: int, user: User = Depends(require_permission("pos.view")), db: Session = Depends(get_db)):
    company = _get_company(db)
    session = _get_session(db, session_id, company.id)
    bills = db.query(PosBill).options(joinedload(PosBill.payments)).filter(PosBill.session_id == session.id, PosBill.status == "completed").all()
    mix: dict[str, float] = {}
    for b in bills:
        for p in b.payments:
            mix[p.method] = mix.get(p.method, 0) + _float(p.amount)
    cash_sales = sum(_float(p.amount) for b in bills for p in b.payments if p.method == "cash")
    refunds = db.query(PosReturn).join(PosBill).filter(PosBill.session_id == session.id).all()
    cash_refunds = sum(_float(r.refund_amount) for r in refunds if r.refund_method == "cash")
    expected = _float(session.opening_float) + cash_sales - cash_refunds
    return PosZReportResponse(
        session=_session_response(session),
        bill_count=len(bills),
        gross_sales=sum(_float(b.subtotal) for b in bills),
        discount_total=sum(_float(b.discount_total) for b in bills),
        net_sales=sum(_float(b.grand_total) for b in bills),
        payment_breakdown=mix,
        cash_opening=_float(session.opening_float),
        cash_sales=cash_sales,
        cash_refunds=cash_refunds,
        cash_expected=expected,
        cash_counted=_float(session.closing_cash_counted) if session.closing_cash_counted is not None else None,
        cash_variance=_float(session.cash_variance) if session.cash_variance is not None else None,
        void_count=0,
        return_count=len(refunds),
    )


# --- Catalog ---

@router.get("/catalog", response_model=list[PosCatalogItemResponse])
def list_catalog(user: User = Depends(require_permission("pos.manage_catalog")), db: Session = Depends(get_db)):
    company = _get_company(db)
    products = db.query(Product).filter(Product.company_id == company.id, Product.status == "active").order_by(Product.name).all()
    settings = _get_settings(db, company)
    return [
        PosCatalogItemResponse(
            id=p.id,
            name=p.name,
            service_code=p.service_code,
            category=p.category,
            sell_at_pos=p.sell_at_pos,
            pos_category=p.pos_category,
            pos_sort_order=p.pos_sort_order or 0,
            price=product_unit_price(p),
            in_stock=_product_in_stock(p, settings),
        )
        for p in products
    ]


@router.put("/catalog/{product_id}", response_model=PosCatalogItemResponse)
def update_catalog(
    product_id: int,
    data: PosCatalogUpdateRequest,
    user: User = Depends(require_permission("pos.manage_catalog")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == company.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    settings = _get_settings(db, company)
    return PosCatalogItemResponse(
        id=product.id,
        name=product.name,
        service_code=product.service_code,
        category=product.category,
        sell_at_pos=product.sell_at_pos,
        pos_category=product.pos_category,
        pos_sort_order=product.pos_sort_order or 0,
        price=product_unit_price(product),
        in_stock=_product_in_stock(product, settings),
    )


# --- Terminal ---

@router.get("/terminal/catalog", response_model=PosCatalogResponse)
def terminal_catalog(
    q: str | None = None,
    category: str | None = None,
    session: PosSession = Depends(_session_dep),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    query = db.query(Product).filter(Product.company_id == company.id, Product.sell_at_pos.is_(True), Product.status == "active")
    if category:
        query = query.filter(Product.pos_category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(Product.name.ilike(like))
    products = query.order_by(Product.pos_sort_order.asc(), Product.name.asc()).all()
    categories = sorted({p.pos_category for p in products if p.pos_category})
    return PosCatalogResponse(
        items=[
            PosProductTerminal(
                id=p.id,
                name=p.name,
                category=p.pos_category or p.category,
                price=product_unit_price(p),
                gst_rate=_float(p.gst_rate),
                in_stock=_product_in_stock(p, settings),
                service_code=p.service_code,
            )
            for p in products
        ],
        categories=categories,
    )


@router.get("/terminal/cart", response_model=PosCartResponse)
def get_cart(session: PosSession = Depends(_session_dep), user: User = Depends(require_permission("pos.bill")), db: Session = Depends(get_db)):
    cart = _get_or_create_active_cart(db, session, user)
    db.commit()
    return _cart_response(_load_cart(db, cart.id))


@router.post("/terminal/cart/items", response_model=PosCartResponse)
def add_cart_item(
    data: PosCartAddRequest,
    session: PosSession = Depends(_session_dep),
    user: User = Depends(require_permission("pos.bill")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    product = _get_pos_product(db, company.id, data.product_id)
    if not _product_in_stock(product, settings):
        raise HTTPException(status_code=400, detail="Product out of stock")
    qty = min(max(float(data.quantity), 1), MAX_LINE_QTY)
    cart = _get_or_create_active_cart(db, session, user)
    existing = next((i for i in cart.items if i.product_id == product.id), None)
    if existing:
        existing.quantity = Decimal(str(min(_float(existing.quantity) + qty, MAX_LINE_QTY)))
    else:
        price = product_unit_price(product)
        gst = _float(product.gst_rate or 18)
        lt, _ = _line_total(qty, price, 0, gst)
        cart.items.append(
            PosCartItem(
                product_id=product.id,
                quantity=Decimal(str(qty)),
                unit_price=Decimal(str(price)),
                gst_rate=Decimal(str(gst)),
                line_total=Decimal(str(lt)),
            )
        )
    _recalc_cart(cart)
    db.commit()
    return _cart_response(_load_cart(db, cart.id))


@router.put("/terminal/cart/items/{item_id}", response_model=PosCartResponse)
def update_cart_item(
    item_id: int,
    data: PosCartUpdateRequest,
    session: PosSession = Depends(_session_dep),
    user: User = Depends(require_permission("pos.bill")),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_active_cart(db, session, user)
    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    if data.quantity is not None:
        item.quantity = Decimal(str(min(max(float(data.quantity), 1), MAX_LINE_QTY)))
    if data.discount_amount is not None:
        item.discount_amount = Decimal(str(max(float(data.discount_amount), 0)))
    _recalc_cart(cart)
    db.commit()
    return _cart_response(_load_cart(db, cart.id))


@router.delete("/terminal/cart/items/{item_id}", response_model=PosCartResponse)
def remove_cart_item(
    item_id: int,
    session: PosSession = Depends(_session_dep),
    user: User = Depends(require_permission("pos.bill")),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_active_cart(db, session, user)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item:
        db.delete(item)
        _recalc_cart(cart)
        db.commit()
    return _cart_response(_load_cart(db, cart.id))


@router.put("/terminal/cart/customer", response_model=PosCartResponse)
def set_cart_customer(
    data: PosCartCustomerRequest,
    session: PosSession = Depends(_session_dep),
    user: User = Depends(require_permission("pos.bill")),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_active_cart(db, session, user)
    if data.customer_name is not None:
        cart.customer_name = data.customer_name
    if data.customer_phone is not None:
        cart.customer_phone = data.customer_phone
    if data.customer_gstin is not None:
        cart.customer_gstin = data.customer_gstin
    if data.contact_id is not None:
        cart.contact_id = data.contact_id
    db.commit()
    return _cart_response(_load_cart(db, cart.id))


@router.post("/terminal/cart/hold", response_model=PosCartResponse)
def hold_cart(
    data: PosCartHoldRequest,
    session: PosSession = Depends(_session_dep),
    user: User = Depends(require_permission("pos.hold")),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_active_cart(db, session, user)
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cannot hold empty cart")
    cart.status = "held"
    cart.held_label = data.held_label.strip()
    db.add(PosCart(company_id=session.company_id, session_id=session.id, created_by_id=user.id))
    db.commit()
    new_cart = _get_or_create_active_cart(db, session, user)
    return _cart_response(_load_cart(db, new_cart.id))


@router.get("/terminal/carts/held", response_model=list[PosCartResponse])
def list_held_carts(session: PosSession = Depends(_session_dep), user: User = Depends(require_permission("pos.hold")), db: Session = Depends(get_db)):
    carts = (
        db.query(PosCart)
        .options(joinedload(PosCart.items).joinedload(PosCartItem.product))
        .filter(PosCart.session_id == session.id, PosCart.status == "held")
        .order_by(PosCart.updated_at.desc())
        .all()
    )
    return [_cart_response(c) for c in carts]


@router.post("/terminal/cart/recall/{cart_id}", response_model=PosCartResponse)
def recall_cart(
    cart_id: int,
    session: PosSession = Depends(_session_dep),
    user: User = Depends(require_permission("pos.hold")),
    db: Session = Depends(get_db),
):
    held = db.query(PosCart).filter(PosCart.id == cart_id, PosCart.session_id == session.id, PosCart.status == "held").first()
    if not held:
        raise HTTPException(status_code=404, detail="Held cart not found")
    active = _get_or_create_active_cart(db, session, user)
    if active.items:
        active.status = "voided"
        db.flush()
    held.status = "active"
    held.held_label = None
    db.commit()
    return _cart_response(_load_cart(db, held.id))


@router.post("/terminal/checkout", response_model=PosCheckoutResponse)
def checkout(
    data: PosCheckoutRequest,
    request: Request,
    session: PosSession = Depends(_session_dep),
    user: User = Depends(require_permission("pos.bill")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    if data.payment_method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Invalid payment method")
    cart = _get_or_create_active_cart(db, session, user)
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    for item in cart.items:
        product = item.product or db.query(Product).filter(Product.id == item.product_id).first()
        if product and product.inventory_tracked and _float(product.on_hand_quantity) < _float(item.quantity):
            if not settings.allow_negative_stock:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")
    _recalc_cart(cart)
    bill_number = _generate_bill_number(db, company.id, settings.bill_number_prefix)
    name = data.customer_name or cart.customer_name or "Walk-in"
    phone = data.customer_phone or cart.customer_phone
    gstin = data.customer_gstin or cart.customer_gstin
    contact_id = data.contact_id or cart.contact_id
    bill = PosBill(
        company_id=company.id,
        bill_number=bill_number,
        session_id=session.id,
        register_id=session.register_id,
        contact_id=contact_id,
        status="completed",
        subtotal=cart.subtotal,
        discount_total=cart.discount_total,
        tax_total=cart.tax_total,
        grand_total=cart.grand_total,
        customer_name=name,
        customer_phone=phone,
        customer_gstin=gstin,
        cashier_id=user.id,
        completed_at=_utcnow(),
    )
    db.add(bill)
    db.flush()
    for item in cart.items:
        product = item.product or db.query(Product).filter(Product.id == item.product_id).first()
        db.add(
            PosBillItem(
                bill_id=bill.id,
                product_id=item.product_id,
                product_name_snapshot=product.name if product else "Product",
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                gst_rate=item.gst_rate,
                line_total=item.line_total,
            )
        )
    db.add(
        PosPayment(
            bill_id=bill.id,
            amount=bill.grand_total,
            method=data.payment_method,
            reference=data.payment_reference,
            status="completed",
        )
    )
    db.flush()
    bill = _get_bill(db, bill.id, company.id)
    if settings.auto_create_invoice:
        inv = _create_invoice_for_bill(db, company, user, bill)
        if inv:
            bill.invoice_id = inv.id
    if settings.inventory_deduct_on_sale:
        for item in bill.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                _deduct_stock(db, product, user, _float(item.quantity), bill_number, settings.allow_negative_stock)
    cart.status = "completed"
    db.add(PosCart(company_id=company.id, session_id=session.id, created_by_id=user.id))
    db.commit()
    change = 0.0
    if data.payment_method == "cash" and data.amount_tendered is not None:
        change = max(float(data.amount_tendered) - _float(bill.grand_total), 0)
    log_activity(db, "pos_sale_completed", user_id=user.id, email=user.email, details=f"bill:{bill_number}", ip_address=get_client_ip(request))
    return PosCheckoutResponse(
        bill_id=bill.id,
        bill_number=bill_number,
        grand_total=_float(bill.grand_total),
        change_due=change,
        payment_method=data.payment_method,
        invoice_id=bill.invoice_id,
        message="Sale completed",
    )


# --- Bills ---

@router.get("/bills", response_model=PosBillListResponse)
def list_bills(
    status: str | None = None,
    user: User = Depends(require_permission("pos.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    q = db.query(PosBill).options(joinedload(PosBill.items), joinedload(PosBill.payments), joinedload(PosBill.cashier)).filter(PosBill.company_id == company.id)
    if status:
        q = q.filter(PosBill.status == status)
    bills = q.order_by(PosBill.completed_at.desc()).limit(200).all()
    return PosBillListResponse(items=[_bill_list_item(b) for b in bills], total=len(bills))


@router.get("/bills/{bill_id}", response_model=PosBillResponse)
def get_bill(bill_id: int, user: User = Depends(require_permission("pos.view")), db: Session = Depends(get_db)):
    company = _get_company(db)
    return _bill_response(_get_bill(db, bill_id, company.id))


@router.get("/bills/{bill_id}/receipt", response_model=PosReceiptResponse)
def get_receipt(bill_id: int, user: User = Depends(require_permission("pos.view")), db: Session = Depends(get_db)):
    company = _get_company(db)
    settings = _get_settings(db, company)
    bill = _get_bill(db, bill_id, company.id)
    return PosReceiptResponse(bill_number=bill.bill_number, html=_receipt_html(company, settings, bill))


@router.post("/bills/{bill_id}/void", response_model=PosBillResponse)
def void_bill(
    bill_id: int,
    data: PosBillVoidRequest,
    request: Request,
    user: User = Depends(require_permission("pos.void")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status != "completed":
        raise HTTPException(status_code=400, detail="Only completed bills can be voided")
    bill.status = "voided"
    bill.voided_at = _utcnow()
    bill.void_reason = data.reason.strip()
    bill.voided_by_id = user.id
    if settings.inventory_deduct_on_sale:
        for item in bill.items:
            if item.product_id:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    _restock(db, product, user, _float(item.quantity), bill.bill_number)
    db.commit()
    log_activity(db, "pos_bill_voided", user_id=user.id, email=user.email, details=f"bill:{bill.bill_number}", ip_address=get_client_ip(request))
    return _bill_response(_get_bill(db, bill_id, company.id))


@router.post("/bills/{bill_id}/returns", response_model=PosReturnListItem)
def process_return(
    bill_id: int,
    data: PosReturnRequest,
    request: Request,
    user: User = Depends(require_permission("pos.return")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status not in ("completed", "partially_returned"):
        raise HTTPException(status_code=400, detail="Cannot return this bill")
    if bill.completed_at and (_utcnow() - bill.completed_at).days > settings.return_window_days:
        raise HTTPException(status_code=400, detail="Return window expired")
    refund = Decimal("0")
    for line in data.items:
        item = next((i for i in bill.items if i.id == line.get("bill_item_id")), None)
        if not item:
            continue
        qty = min(float(line.get("quantity", 0)), _float(item.quantity))
        refund += Decimal(str(qty * _float(item.unit_price)))
        if settings.inventory_deduct_on_sale and item.product_id:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                _restock(db, product, user, qty, bill.bill_number)
    ret = PosReturn(
        company_id=company.id,
        bill_id=bill.id,
        return_number=_generate_return_number(db, company.id),
        reason=data.reason.strip(),
        refund_amount=refund,
        refund_method=data.refund_method,
        items_json=data.items,
        processed_by_id=user.id,
    )
    db.add(ret)
    bill.status = "returned" if refund >= bill.grand_total else "partially_returned"
    db.commit()
    log_activity(db, "pos_return_processed", user_id=user.id, email=user.email, details=f"bill:{bill.bill_number}", ip_address=get_client_ip(request))
    return PosReturnListItem(
        id=ret.id,
        return_number=ret.return_number,
        bill_number=bill.bill_number,
        status=ret.status,
        reason=ret.reason,
        refund_amount=_float(ret.refund_amount),
        processed_at=ret.processed_at,
    )


@router.get("/returns", response_model=PosReturnListResponse)
def list_returns(user: User = Depends(require_permission("pos.view")), db: Session = Depends(get_db)):
    company = _get_company(db)
    rows = (
        db.query(PosReturn, PosBill)
        .join(PosBill, PosBill.id == PosReturn.bill_id)
        .filter(PosReturn.company_id == company.id)
        .order_by(PosReturn.processed_at.desc())
        .limit(100)
        .all()
    )
    items = [
        PosReturnListItem(
            id=ret.id,
            return_number=ret.return_number,
            bill_number=bill.bill_number,
            status=ret.status,
            reason=ret.reason,
            refund_amount=_float(ret.refund_amount),
            processed_at=ret.processed_at,
        )
        for ret, bill in rows
    ]
    return PosReturnListResponse(items=items, total=len(items))
