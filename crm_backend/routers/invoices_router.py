from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import FRONTEND_URL, STAFF_ROLES
from company_branding import build_company_branding
from invoice_config import (
    ALLOWED_TRANSITIONS,
    COMPANY_CIN,
    COMPANY_INVOICE_DISPLAY_NAME,
    COMPANY_TAGLINE,
    CONVERTIBLE_ORDER_STATUSES,
    CONVERTIBLE_QUOTE_STATUSES,
    DEFAULT_BANK_INSTRUCTIONS,
    DEFAULT_BILLING_NOTES,
    DEFAULT_CLIENT_NATURE,
    DEFAULT_ORG_TYPE,
    DEFAULT_PAYMENT_TERMS,
    DEFAULT_SIGNATORY,
    EDITABLE_STATUSES,
    FINAL_STATUSES,
    INVOICE_DOCUMENT_TITLE,
    INVOICE_STATUS_LABELS,
    INVOICE_STATUSES,
    INVOICE_TERMS_LABEL,
    INVOICE_TYPES,
    REVIEW_THRESHOLD,
    SOURCE_TYPES,
)
from models import (
    Company,
    Contact,
    Deal,
    Invoice,
    InvoiceLineItem,
    InvoicePayment,
    Product,
    Quotation,
    SalesOrder,
    SystemSetting,
    User,
)
from services.document_number_service import generate_invoice_number
from schemas import (
    InvoiceCreateRequest,
    InvoiceDefaultsResponse,
    InvoiceLineItemFields,
    InvoiceLineItemResponse,
    InvoiceListResponse,
    InvoicePaymentFields,
    InvoicePaymentResponse,
    InvoicePublicResponse,
    InvoiceReasonRequest,
    InvoiceResponse,
    InvoiceReviewRequest,
    InvoiceSendRequest,
    InvoiceStatsResponse,
    InvoiceStatusOption,
    InvoiceUpdateRequest,
    QuotationCompanyBranding,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])
public_router = APIRouter(prefix="/public/invoices", tags=["public-invoices"])




def _decimal(v) -> Decimal:
    return Decimal("0") if v is None else Decimal(str(v))


def _float(v) -> float:
    return 0.0 if v is None else float(v)


def _validate_status(status: str) -> None:
    if status not in INVOICE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(INVOICE_STATUSES)}")


def _set_status(inv: Invoice, new_status: str) -> None:
    _validate_status(new_status)
    allowed = ALLOWED_TRANSITIONS.get(inv.status, set())
    if new_status not in allowed and inv.status != new_status:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {inv.status} to {new_status}")
    inv.status = new_status
    inv.last_status_change_at = datetime.now(timezone.utc)


def _get_invoice(db: Session, invoice_id: int, company_id: int) -> Invoice:
    inv = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.assigned_to),
            joinedload(Invoice.created_by),
            joinedload(Invoice.reviewed_by),
            joinedload(Invoice.issued_by),
            joinedload(Invoice.sales_order),
            joinedload(Invoice.quotation),
            joinedload(Invoice.deal),
            joinedload(Invoice.contact),
            joinedload(Invoice.line_items).joinedload(InvoiceLineItem.product),
            joinedload(Invoice.payments).joinedload(InvoicePayment.recorded_by),
        )
        .filter(Invoice.id == invoice_id, Invoice.company_id == company_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


def _get_by_token(db: Session, token: str) -> Invoice:
    inv = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.line_items),
            joinedload(Invoice.payments),
            joinedload(Invoice.company),
        )
        .filter(Invoice.share_token == token)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


def _validate_staff(db: Session, uid: int | None, company_id: int):
    if uid is None:
        return
    if not db.query(User).filter(User.id == uid, User.company_id == company_id, User.role.in_(STAFF_ROLES), User.status == "active").first():
        raise HTTPException(status_code=400, detail="Invalid staff member")


def _compute_totals(items, hdr_amt, hdr_pct, round_off=0) -> dict:
    subtotal = Decimal("0")
    line_disc = Decimal("0")
    total_tax = Decimal("0")
    for item in items:
        qty = _decimal(item.quantity if hasattr(item, "quantity") else item["quantity"])
        price = _decimal(item.unit_price if hasattr(item, "unit_price") else item["unit_price"])
        dp = _decimal(item.discount_percent if hasattr(item, "discount_percent") else item["discount_percent"])
        da = _decimal(item.discount_amount if hasattr(item, "discount_amount") else item["discount_amount"])
        tr = _decimal(item.tax_rate if hasattr(item, "tax_rate") else item["tax_rate"])
        ls = qty * price
        ld = da if da > 0 else ls * (dp / Decimal("100"))
        ad = max(ls - ld, Decimal("0"))
        total_tax += ad * (tr / Decimal("100"))
        subtotal += ls
        line_disc += ld
    after = max(subtotal - line_disc, Decimal("0"))
    ha = _decimal(hdr_amt)
    hp = _decimal(hdr_pct)
    hd = ha if ha > 0 else after * (hp / Decimal("100"))
    taxable = max(after - hd, Decimal("0"))
    tax_scale = taxable / after if after > 0 else Decimal("0")
    total_tax *= tax_scale
    ro = _decimal(round_off)
    grand = taxable + total_tax + ro
    return {"subtotal": subtotal, "line_discount_total": line_disc, "header_discount_amount": hd, "header_discount_percent": hp, "total_tax": total_tax, "round_off": ro, "grand_total": grand}


def _generate_number(db: Session, company: Company) -> str:
    return generate_invoice_number(db, company)


def _line_resp(li: InvoiceLineItem) -> InvoiceLineItemResponse:
    return InvoiceLineItemResponse(
        id=li.id, product_id=li.product_id, product_name=li.product.name if li.product else None,
        sales_order_line_item_id=li.sales_order_line_item_id, sort_order=li.sort_order, section=li.section,
        item_name=li.item_name, description=li.description, quantity=_float(li.quantity), unit=li.unit,
        unit_price=_float(li.unit_price), discount_percent=_float(li.discount_percent),
        discount_amount=_float(li.discount_amount), tax_rate=_float(li.tax_rate),
        line_subtotal=_float(li.line_subtotal), line_total=_float(li.line_total),
    )


def _pay_resp(p: InvoicePayment) -> InvoicePaymentResponse:
    return InvoicePaymentResponse(
        id=p.id, amount=_float(p.amount), payment_date=p.payment_date, payment_method=p.payment_method,
        reference=p.reference, note=p.note, recorded_by_id=p.recorded_by_id,
        recorded_by_name=p.recorded_by.name if p.recorded_by else None, created_at=p.created_at,
    )


def _inv_resp(inv: Invoice) -> InvoiceResponse:
    share_url = f"{FRONTEND_URL}/invoice/{inv.share_token}" if inv.share_token else None
    return InvoiceResponse(
        id=inv.id, company_id=inv.company_id, invoice_number=inv.invoice_number, title=inv.title,
        status=inv.status, version=inv.version, invoice_type=inv.invoice_type, source_type=inv.source_type,
        currency=inv.currency, issue_date=inv.issue_date, due_date=inv.due_date,
        sales_order_id=inv.sales_order_id, sales_order_number=inv.sales_order.order_number if inv.sales_order else None,
        quotation_id=inv.quotation_id, quotation_number=inv.quotation.quote_number if inv.quotation else None,
        deal_id=inv.deal_id, deal_title=inv.deal.title if inv.deal else None,
        contact_id=inv.contact_id, contact_name=inv.contact.name if inv.contact else None,
        assigned_to_id=inv.assigned_to_id, assigned_to_name=inv.assigned_to.name if inv.assigned_to else None,
        assigned_to_email=inv.assigned_to.email if inv.assigned_to else None,
        created_by_id=inv.created_by_id, created_by_name=inv.created_by.name if inv.created_by else None,
        reviewed_by_id=inv.reviewed_by_id, reviewed_by_name=inv.reviewed_by.name if inv.reviewed_by else None,
        issued_by_id=inv.issued_by_id, issued_by_name=inv.issued_by.name if inv.issued_by else None,
        parent_invoice_id=inv.parent_invoice_id, root_invoice_id=inv.root_invoice_id,
        client_name=inv.client_name, client_email=inv.client_email, client_phone=inv.client_phone,
        client_org=inv.client_org, client_gstin=inv.client_gstin, attention_to=inv.attention_to,
        billing_address=inv.billing_address,
        subtotal=_float(inv.subtotal), line_discount_total=_float(inv.line_discount_total),
        header_discount_amount=_float(inv.header_discount_amount), header_discount_percent=_float(inv.header_discount_percent),
        total_tax=_float(inv.total_tax), round_off=_float(inv.round_off), grand_total=_float(inv.grand_total),
        amount_paid=_float(inv.amount_paid), outstanding_amount=_float(inv.outstanding_amount),
        write_off_amount=_float(inv.write_off_amount),
        payment_terms=inv.payment_terms, bank_instructions=inv.bank_instructions, billing_notes=inv.billing_notes,
        internal_notes=inv.internal_notes, review_comments=inv.review_comments,
        cancellation_reason=inv.cancellation_reason, adjustment_reason=inv.adjustment_reason,
        requires_review=bool(inv.requires_review), share_token=inv.share_token, share_url=share_url,
        reviewed_at=inv.reviewed_at, approved_at=inv.approved_at, issued_at=inv.issued_at,
        sent_at=inv.sent_at, viewed_at=inv.viewed_at, closed_at=inv.closed_at, cancelled_at=inv.cancelled_at,
        last_status_change_at=inv.last_status_change_at, last_payment_at=inv.last_payment_at,
        line_items=[_line_resp(li) for li in inv.line_items],
        payments=sorted([_pay_resp(p) for p in inv.payments], key=lambda x: x.payment_date or datetime.min, reverse=True),
        created_at=inv.created_at, updated_at=inv.updated_at,
    )


def _branding(company: Company, settings: SystemSetting | None) -> QuotationCompanyBranding:
    return build_company_branding(company, settings, for_invoice=True)


def _is_overdue(inv: Invoice) -> bool:
    if not inv.due_date or _float(inv.outstanding_amount) <= 0:
        return False
    due = inv.due_date if inv.due_date.tzinfo else inv.due_date.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > due and inv.status in {"issued", "sent", "viewed", "partially_paid", "overdue"}


def _check_overdue(inv: Invoice) -> None:
    if _is_overdue(inv) and inv.status in {"issued", "sent", "viewed", "partially_paid"}:
        inv.status = "overdue"


def _apply_lines(inv: Invoice, items: list, db: Session) -> None:
    inv.line_items.clear()
    for idx, item in enumerate(items):
        if item.product_id:
            if not db.query(Product).filter(Product.id == item.product_id, Product.company_id == inv.company_id).first():
                raise HTTPException(status_code=400, detail="Invalid product")
        qty, price = _decimal(item.quantity), _decimal(item.unit_price)
        dp, da, tr = _decimal(item.discount_percent), _decimal(item.discount_amount), _decimal(item.tax_rate)
        ls = qty * price
        ld = da if da > 0 else ls * (dp / Decimal("100"))
        ad = max(ls - ld, Decimal("0"))
        lt = ad + ad * (tr / Decimal("100"))
        inv.line_items.append(InvoiceLineItem(
            product_id=item.product_id, sales_order_line_item_id=item.sales_order_line_item_id,
            sort_order=item.sort_order or idx, section=item.section, item_name=item.item_name.strip(),
            description=item.description, quantity=qty, unit=item.unit or "Service", unit_price=price,
            discount_percent=dp, discount_amount=da, tax_rate=tr, line_subtotal=ls, line_total=lt,
        ))


def _sync_balances(inv: Invoice) -> None:
    paid = sum(_decimal(p.amount) for p in inv.payments)
    inv.amount_paid = paid
    inv.outstanding_amount = max(_decimal(inv.grand_total) - paid - _decimal(inv.write_off_amount), Decimal("0"))
    if _float(inv.outstanding_amount) <= 0 and inv.status not in {"draft", "cancelled", "closed", "written_off", "refunded"}:
        if inv.status in {"issued", "sent", "viewed", "partially_paid", "overdue"}:
            inv.status = "paid"
            inv.last_status_change_at = datetime.now(timezone.utc)
    elif paid > 0 and inv.status in {"issued", "sent", "viewed", "overdue"}:
        inv.status = "partially_paid"
        inv.last_status_change_at = datetime.now(timezone.utc)


def _build_invoice(db, company, payload: InvoiceCreateRequest, user, *, source_type="manual", source_ids=None) -> Invoice:
    source_ids = source_ids or {}
    if payload.invoice_type not in INVOICE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid invoice type")
    issue = payload.issue_date or datetime.now(timezone.utc)
    if payload.due_date and issue and payload.due_date < issue:
        raise HTTPException(status_code=400, detail="Due date cannot precede issue date")
    totals = _compute_totals(payload.line_items, payload.header_discount_amount, payload.header_discount_percent, payload.round_off)
    needs_review = _float(totals["grand_total"]) > REVIEW_THRESHOLD or source_type == "manual"
    inv = Invoice(
        company_id=company.id, created_by_id=user.id, title=payload.title.strip(), status="draft",
        invoice_type=payload.invoice_type, source_type=source_type, currency=payload.currency or company.currency,
        issue_date=issue, due_date=payload.due_date,
        sales_order_id=source_ids.get("sales_order_id") or payload.sales_order_id,
        quotation_id=source_ids.get("quotation_id") or payload.quotation_id,
        deal_id=payload.deal_id, contact_id=payload.contact_id, assigned_to_id=payload.assigned_to_id or user.id,
        client_name=payload.client_name, client_email=payload.client_email, client_phone=payload.client_phone,
        client_org=payload.client_org, client_gstin=payload.client_gstin, attention_to=payload.attention_to,
        billing_address=payload.billing_address,
        subtotal=totals["subtotal"], line_discount_total=totals["line_discount_total"],
        header_discount_amount=totals["header_discount_amount"], header_discount_percent=totals["header_discount_percent"],
        total_tax=totals["total_tax"], round_off=totals["round_off"], grand_total=totals["grand_total"],
        outstanding_amount=totals["grand_total"], amount_paid=Decimal("0"),
        payment_terms=payload.payment_terms or DEFAULT_PAYMENT_TERMS,
        bank_instructions=payload.bank_instructions or DEFAULT_BANK_INSTRUCTIONS,
        billing_notes=payload.billing_notes or DEFAULT_BILLING_NOTES, internal_notes=payload.internal_notes,
        requires_review=1 if needs_review else 0,
    )
    db.add(inv)
    db.flush()
    _apply_lines(inv, payload.line_items, db)
    return inv


def _from_order(order: SalesOrder) -> InvoiceCreateRequest:
    due = order.due_date or (datetime.now(timezone.utc) + timedelta(days=15))
    return InvoiceCreateRequest(
        title=f"Invoice — {order.title}", invoice_type="standard", currency=order.currency,
        issue_date=datetime.now(timezone.utc), due_date=due,
        sales_order_id=order.id, quotation_id=order.quotation_id, deal_id=order.deal_id,
        contact_id=order.contact_id, assigned_to_id=order.assigned_to_id,
        client_name=order.client_name, client_email=order.client_email, client_phone=order.client_phone,
        client_org=order.client_org, attention_to=order.attention_to,
        billing_address=order.billing_address,
        header_discount_amount=_float(order.header_discount_amount),
        header_discount_percent=_float(order.header_discount_percent),
        payment_terms=order.billing_notes or order.payment_milestone_notes,
        billing_notes=order.delivery_instructions,
        internal_notes=f"Generated from order {order.order_number}",
        line_items=[InvoiceLineItemFields(
            product_id=li.product_id, sales_order_line_item_id=li.id, sort_order=li.sort_order,
            section=li.section, item_name=li.item_name, description=li.description,
            quantity=_float(li.quantity), unit=li.unit, unit_price=_float(li.unit_price),
            discount_percent=_float(li.discount_percent), discount_amount=_float(li.discount_amount),
            tax_rate=_float(li.tax_rate),
        ) for li in order.line_items],
    )


def _from_quote(quote: Quotation) -> InvoiceCreateRequest:
    due = quote.valid_until or (datetime.now(timezone.utc) + timedelta(days=15))
    return InvoiceCreateRequest(
        title=f"Invoice — {quote.title}", invoice_type="standard", currency=quote.currency,
        issue_date=datetime.now(timezone.utc), due_date=due,
        quotation_id=quote.id, deal_id=quote.deal_id, contact_id=quote.contact_id,
        assigned_to_id=quote.assigned_to_id, client_name=quote.client_name, client_email=quote.client_email,
        client_org=quote.client_org, attention_to=quote.attention_to, billing_address=quote.billing_address,
        header_discount_amount=_float(quote.header_discount_amount),
        header_discount_percent=_float(quote.header_discount_percent),
        payment_terms=quote.payment_terms, billing_notes=quote.deliverables,
        internal_notes=f"Generated from quotation {quote.quote_number}",
        line_items=[InvoiceLineItemFields(
            product_id=li.product_id, sort_order=li.sort_order, section=li.section,
            item_name=li.item_name, description=li.description, quantity=_float(li.quantity),
            unit=li.unit, unit_price=_float(li.unit_price), discount_percent=_float(li.discount_percent),
            discount_amount=_float(li.discount_amount), tax_rate=_float(li.tax_rate),
        ) for li in quote.line_items],
    )


@router.get("/statuses", response_model=list[InvoiceStatusOption])
def statuses(_: User = Depends(require_permission("invoices.view"))):
    return [InvoiceStatusOption(value=s, label=INVOICE_STATUS_LABELS[s]) for s in INVOICE_STATUSES]


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def assignees(user: User = Depends(require_permission("invoices.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    staff = db.query(User).filter(User.company_id == company.id, User.role.in_(STAFF_ROLES), User.status == "active").order_by(User.name).all()
    return [StaffAssigneeResponse(id=u.id, name=u.name, email=u.email, role=u.role) for u in staff]


@router.get("/stats/summary", response_model=InvoiceStatsResponse)
def stats(user: User = Depends(require_permission("invoices.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    rows = db.query(Invoice.status, func.count(Invoice.id)).filter(Invoice.company_id == company.id).group_by(Invoice.status).all()
    counts = {s: 0 for s in INVOICE_STATUSES}
    for s, c in rows:
        counts[s] = c
    billed = db.query(func.coalesce(func.sum(Invoice.grand_total), 0)).filter(Invoice.company_id == company.id, Invoice.status.notin_(["draft", "cancelled"])).scalar()
    collected = db.query(func.coalesce(func.sum(Invoice.amount_paid), 0)).filter(Invoice.company_id == company.id).scalar()
    outstanding = db.query(func.coalesce(func.sum(Invoice.outstanding_amount), 0)).filter(
        Invoice.company_id == company.id, Invoice.status.in_(["issued", "sent", "viewed", "partially_paid", "overdue"])
    ).scalar()
    return InvoiceStatsResponse(
        total=sum(counts.values()), draft=counts["draft"], awaiting_review=counts["awaiting_review"],
        issued=counts["issued"], sent=counts["sent"], partially_paid=counts["partially_paid"],
        paid=counts["paid"], overdue=counts["overdue"],
        total_billed=float(billed or 0), total_collected=float(collected or 0), total_outstanding=float(outstanding or 0),
    )


@router.get("/review-queue", response_model=InvoiceListResponse)
def review_queue(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                 user: User = Depends(require_permission("invoices.review")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    q = db.query(Invoice).options(joinedload(Invoice.line_items), joinedload(Invoice.assigned_to)).filter(
        Invoice.company_id == company.id, Invoice.status == "awaiting_review"
    ).order_by(Invoice.updated_at.desc())
    total = q.count()
    items = q.offset((page - 1) * limit).limit(limit).all()
    return InvoiceListResponse(items=[_inv_resp(i) for i in items], total=total, page=page, limit=limit)


@router.get("", response_model=InvoiceListResponse)
def list_invoices(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), status: str | None = None,
                  source_type: str | None = None, search: str | None = None, owner_id: int | None = None,
                  payment_filter: str | None = None, sort_by: str = "updated_at", sort_dir: str = "desc",
                  user: User = Depends(require_permission("invoices.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    q = db.query(Invoice).options(joinedload(Invoice.assigned_to), joinedload(Invoice.sales_order),
                                  joinedload(Invoice.quotation), joinedload(Invoice.line_items)).filter(Invoice.company_id == company.id)
    if status:
        _validate_status(status)
        q = q.filter(Invoice.status == status)
    if source_type:
        q = q.filter(Invoice.source_type == source_type)
    if owner_id:
        q = q.filter(Invoice.assigned_to_id == owner_id)
    if search:
        t = f"%{search.strip()}%"
        q = q.filter(or_(Invoice.invoice_number.ilike(t), Invoice.title.ilike(t), Invoice.client_name.ilike(t)))
    if payment_filter == "overdue":
        q = q.filter(Invoice.status == "overdue")
    elif payment_filter == "partially_paid":
        q = q.filter(Invoice.status == "partially_paid")
    elif payment_filter == "outstanding":
        q = q.filter(Invoice.outstanding_amount > 0, Invoice.status.notin_(list(FINAL_STATUSES)))
    col = {"updated_at": Invoice.updated_at, "due_date": Invoice.due_date, "grand_total": Invoice.grand_total,
           "outstanding_amount": Invoice.outstanding_amount, "issue_date": Invoice.issue_date}.get(sort_by, Invoice.updated_at)
    q = q.order_by(col.asc() if sort_dir == "asc" else col.desc())
    total = q.count()
    items = q.offset((page - 1) * limit).limit(limit).all()
    for i in items:
        _check_overdue(i)
    db.commit()
    return InvoiceListResponse(items=[_inv_resp(i) for i in items], total=total, page=page, limit=limit)


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(payload: InvoiceCreateRequest, request: Request,
                   user: User = Depends(require_permission("invoices.create")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    if not payload.client_name and not payload.contact_id:
        raise HTTPException(status_code=400, detail="Customer is required")
    inv = _build_invoice(db, company, payload, user)
    db.commit()
    inv = _get_invoice(db, inv.id, company.id)
    log_activity(db, "invoice_created", user_id=user.id, email=user.email, details=f"Invoice draft created", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.post("/from-order/{order_id}", response_model=InvoiceResponse, status_code=201)
def from_order(order_id: int, request: Request, user: User = Depends(require_permission("invoices.generate_from_order")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = db.query(SalesOrder).options(joinedload(SalesOrder.line_items)).filter(SalesOrder.id == order_id, SalesOrder.company_id == company.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if order.status not in CONVERTIBLE_ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Sales order is not ready for invoicing")
    if not order.line_items:
        raise HTTPException(status_code=400, detail="Order has no line items")
    inv = _build_invoice(db, company, _from_order(order), user, source_type="sales_order", source_ids={"sales_order_id": order.id, "quotation_id": order.quotation_id})
    db.commit()
    inv = _get_invoice(db, inv.id, company.id)
    log_activity(db, "invoice_generated_from_order", user_id=user.id, email=user.email, details=f"Invoice from order {order.order_number}", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.post("/from-quotation/{quote_id}", response_model=InvoiceResponse, status_code=201)
def from_quotation(quote_id: int, request: Request, user: User = Depends(require_permission("invoices.generate_from_order")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    quote = db.query(Quotation).options(joinedload(Quotation.line_items)).filter(Quotation.id == quote_id, Quotation.company_id == company.id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quote.status not in CONVERTIBLE_QUOTE_STATUSES:
        raise HTTPException(status_code=400, detail="Quotation is not approved for invoicing")
    inv = _build_invoice(db, company, _from_quote(quote), user, source_type="quotation", source_ids={"quotation_id": quote.id})
    db.commit()
    inv = _get_invoice(db, inv.id, company.id)
    log_activity(db, "invoice_generated_from_quote", user_id=user.id, email=user.email, details=f"Invoice from {quote.quote_number}", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.get("/defaults", response_model=InvoiceDefaultsResponse)
def invoice_defaults(_: User = Depends(require_permission("invoices.view"))):
    return InvoiceDefaultsResponse(
        payment_terms=DEFAULT_PAYMENT_TERMS,
        bank_instructions=DEFAULT_BANK_INSTRUCTIONS,
        billing_notes=DEFAULT_BILLING_NOTES,
        document_title=INVOICE_DOCUMENT_TITLE,
        company_display_name=COMPANY_INVOICE_DISPLAY_NAME,
        tagline=COMPANY_TAGLINE,
        cin=COMPANY_CIN,
        signatory_name=DEFAULT_SIGNATORY,
        org_type=DEFAULT_ORG_TYPE,
        client_nature=DEFAULT_CLIENT_NATURE,
        terms_label=INVOICE_TERMS_LABEL,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: int, user: User = Depends(require_permission("invoices.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    _check_overdue(inv)
    db.commit()
    return _inv_resp(inv)


@router.put("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(invoice_id: int, payload: InvoiceUpdateRequest, request: Request,
                   user: User = Depends(require_permission("invoices.edit_draft")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Only draft or awaiting review invoices can be edited")
    totals = _compute_totals(payload.line_items, payload.header_discount_amount, payload.header_discount_percent, payload.round_off)
    inv.title = payload.title.strip()
    inv.invoice_type = payload.invoice_type
    inv.issue_date = payload.issue_date
    inv.due_date = payload.due_date
    inv.client_name = payload.client_name
    inv.client_email = payload.client_email
    inv.client_phone = payload.client_phone
    inv.client_org = payload.client_org
    inv.client_gstin = payload.client_gstin
    inv.billing_address = payload.billing_address
    inv.subtotal = totals["subtotal"]
    inv.line_discount_total = totals["line_discount_total"]
    inv.header_discount_amount = totals["header_discount_amount"]
    inv.header_discount_percent = totals["header_discount_percent"]
    inv.total_tax = totals["total_tax"]
    inv.round_off = totals["round_off"]
    inv.grand_total = totals["grand_total"]
    inv.outstanding_amount = totals["grand_total"] - inv.amount_paid - inv.write_off_amount
    inv.payment_terms = payload.payment_terms
    inv.bank_instructions = payload.bank_instructions
    inv.billing_notes = payload.billing_notes
    inv.internal_notes = payload.internal_notes
    _apply_lines(inv, payload.line_items, db)
    _sync_balances(inv)
    db.commit()
    inv = _get_invoice(db, invoice_id, company.id)
    log_activity(db, "invoice_updated", user_id=user.id, email=user.email, details=f"Invoice {inv.invoice_number or inv.id} updated", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(
    invoice_id: int,
    request: Request,
    user: User = Depends(require_permission("invoices.edit_draft")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft invoices can be deleted")
    number = inv.invoice_number or str(inv.id)
    db.delete(inv)
    db.commit()
    log_activity(
        db,
        "invoice_deleted",
        user_id=user.id,
        email=user.email,
        details=f"Deleted draft invoice {number}",
        ip_address=get_client_ip(request),
    )


@router.post("/{invoice_id}/submit-review", response_model=InvoiceResponse)
def submit_review(invoice_id: int, request: Request, user: User = Depends(require_permission("invoices.edit_draft")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status != "draft" or not inv.line_items:
        raise HTTPException(status_code=400, detail="Draft with line items required")
    if inv.requires_review:
        _set_status(inv, "awaiting_review")
    else:
        _set_status(inv, "approved")
        inv.approved_at = datetime.now(timezone.utc)
    db.commit()
    inv = _get_invoice(db, invoice_id, company.id)
    log_activity(db, "invoice_submitted_review", user_id=user.id, email=user.email, details=f"Invoice submitted for review", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.post("/{invoice_id}/approve", response_model=InvoiceResponse)
def approve(invoice_id: int, payload: InvoiceReviewRequest, request: Request,
            user: User = Depends(require_permission("invoices.review")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status != "awaiting_review":
        raise HTTPException(status_code=400, detail="Invoice not awaiting review")
    _set_status(inv, "approved")
    inv.reviewed_by_id = user.id
    inv.reviewed_at = datetime.now(timezone.utc)
    inv.approved_at = datetime.now(timezone.utc)
    inv.review_comments = payload.comments
    db.commit()
    inv = _get_invoice(db, invoice_id, company.id)
    log_activity(db, "invoice_approved", user_id=user.id, email=user.email, details="Invoice approved", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.post("/{invoice_id}/reject-review", response_model=InvoiceResponse)
def reject_review(invoice_id: int, payload: InvoiceReviewRequest, request: Request,
                  user: User = Depends(require_permission("invoices.review")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    _set_status(inv, "draft")
    inv.review_comments = payload.comments
    db.commit()
    return _inv_resp(_get_invoice(db, invoice_id, company.id))


@router.post("/{invoice_id}/issue", response_model=InvoiceResponse)
def issue(invoice_id: int, request: Request, user: User = Depends(require_permission("invoices.issue")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status not in {"approved", "draft"}:
        raise HTTPException(status_code=400, detail="Invoice must be approved before issue")
    if not inv.line_items:
        raise HTTPException(status_code=400, detail="Line items required")
    if not inv.invoice_number:
        inv.invoice_number = _generate_number(db, company)
    _set_status(inv, "issued")
    inv.issued_at = datetime.now(timezone.utc)
    inv.issued_by_id = user.id
    if not inv.share_token:
        inv.share_token = secrets.token_urlsafe(32)
    db.commit()
    inv = _get_invoice(db, invoice_id, company.id)
    log_activity(db, "invoice_issued", user_id=user.id, email=user.email, details=f"Invoice {inv.invoice_number} issued", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.post("/{invoice_id}/send", response_model=InvoiceResponse)
def send_invoice(invoice_id: int, payload: InvoiceSendRequest, request: Request,
                 user: User = Depends(require_permission("invoices.send")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status not in {"issued", "sent", "viewed", "partially_paid", "overdue"}:
        raise HTTPException(status_code=400, detail="Invoice must be issued first")
    recipient = payload.recipient_email or inv.client_email
    if not recipient:
        raise HTTPException(status_code=400, detail="Client email required")
    if not inv.share_token:
        inv.share_token = secrets.token_urlsafe(32)
    inv.client_email = recipient
    if inv.status == "issued":
        _set_status(inv, "sent")
    inv.sent_at = datetime.now(timezone.utc)
    db.commit()
    inv = _get_invoice(db, invoice_id, company.id)
    share_url = f"{FRONTEND_URL}/invoice/{inv.share_token}"
    try:
        from services.email_service import render_template, send_email
        html = render_template("invoice_sent.html", company_name=company.display_name, invoice_number=inv.invoice_number,
                               client_name=inv.client_name or "Client", grand_total=f"{inv.currency} {_float(inv.grand_total):,.2f}",
                               due_date=inv.due_date.strftime("%d %b %Y") if inv.due_date else "TBD", share_url=share_url, message=payload.message or "")
        send_email(recipient, f"Invoice {inv.invoice_number} from {company.display_name}", html)
    except Exception:
        pass
    log_activity(db, "invoice_sent", user_id=user.id, email=user.email, details=f"Invoice {inv.invoice_number} sent", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.post("/{invoice_id}/record-payment", response_model=InvoiceResponse)
def record_payment(invoice_id: int, payload: InvoicePaymentFields, request: Request,
                   user: User = Depends(require_permission("invoices.record_payment")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status in {"draft", "cancelled", "closed"}:
        raise HTTPException(status_code=400, detail="Cannot record payment on this invoice")
    if _decimal(payload.amount) > _decimal(inv.outstanding_amount):
        raise HTTPException(status_code=400, detail="Payment exceeds outstanding balance")
    inv.payments.append(InvoicePayment(
        amount=_decimal(payload.amount), payment_date=payload.payment_date,
        payment_method=payload.payment_method, reference=payload.reference, note=payload.note, recorded_by_id=user.id,
    ))
    inv.last_payment_at = datetime.now(timezone.utc)
    _sync_balances(inv)
    db.commit()
    inv = _get_invoice(db, invoice_id, company.id)
    action = "invoice_paid" if inv.status == "paid" else "invoice_payment_recorded"
    log_activity(db, action, user_id=user.id, email=user.email, details=f"Payment {_float(payload.amount)} on {inv.invoice_number}", ip_address=get_client_ip(request))
    return _inv_resp(inv)


@router.post("/{invoice_id}/credit-note", response_model=InvoiceResponse, status_code=201)
def credit_note(invoice_id: int, payload: InvoiceReasonRequest, request: Request,
                user: User = Depends(require_permission("invoices.create_adjustment")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    original = _get_invoice(db, invoice_id, company.id)
    if original.status not in {"issued", "sent", "viewed", "partially_paid", "paid", "overdue"}:
        raise HTTPException(status_code=400, detail="Cannot create credit note for this invoice")
    cpayload = InvoiceCreateRequest(
        title=f"Credit Note — {original.title}", invoice_type="credit_note", currency=original.currency,
        issue_date=datetime.now(timezone.utc), due_date=original.due_date,
        sales_order_id=original.sales_order_id, quotation_id=original.quotation_id,
        client_name=original.client_name, client_email=original.client_email, client_org=original.client_org,
        billing_address=original.billing_address, internal_notes=f"Credit note for {original.invoice_number}: {payload.reason}",
        line_items=[InvoiceLineItemFields(item_name=f"Credit — {li.item_name}", quantity=_float(li.quantity),
                     unit=li.unit, unit_price=-_float(li.unit_price), tax_rate=_float(li.tax_rate)) for li in original.line_items],
    )
    cn = _build_invoice(db, company, cpayload, user, source_type=original.source_type)
    cn.parent_invoice_id = original.id
    cn.root_invoice_id = original.root_invoice_id or original.id
    cn.adjustment_reason = payload.reason
    db.commit()
    cn = _get_invoice(db, cn.id, company.id)
    log_activity(db, "invoice_adjustment_created", user_id=user.id, email=user.email, details=f"Credit note for {original.invoice_number}", ip_address=get_client_ip(request))
    return _inv_resp(cn)


@router.post("/{invoice_id}/cancel", response_model=InvoiceResponse)
def cancel(invoice_id: int, payload: InvoiceReasonRequest, request: Request,
           user: User = Depends(require_permission("invoices.cancel")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status in FINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Invoice already finalized")
    inv.status = "cancelled"
    inv.cancellation_reason = payload.reason
    inv.cancelled_at = datetime.now(timezone.utc)
    inv.last_status_change_at = datetime.now(timezone.utc)
    db.commit()
    log_activity(db, "invoice_cancelled", user_id=user.id, email=user.email, details=f"Invoice cancelled: {payload.reason}", ip_address=get_client_ip(request))
    return _inv_resp(_get_invoice(db, invoice_id, company.id))


@router.post("/{invoice_id}/write-off", response_model=InvoiceResponse)
def write_off(invoice_id: int, payload: InvoiceReasonRequest, request: Request,
              user: User = Depends(require_permission("invoices.write_off")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if _float(inv.outstanding_amount) <= 0:
        raise HTTPException(status_code=400, detail="No outstanding balance")
    inv.write_off_amount = inv.outstanding_amount
    inv.outstanding_amount = Decimal("0")
    inv.status = "written_off"
    inv.adjustment_reason = payload.reason
    inv.last_status_change_at = datetime.now(timezone.utc)
    db.commit()
    log_activity(db, "invoice_written_off", user_id=user.id, email=user.email, details=payload.reason, ip_address=get_client_ip(request))
    return _inv_resp(_get_invoice(db, invoice_id, company.id))


@router.post("/{invoice_id}/close", response_model=InvoiceResponse)
def close(invoice_id: int, request: Request, user: User = Depends(require_permission("invoices.cancel")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if inv.status not in {"paid", "cancelled", "refunded", "written_off"}:
        raise HTTPException(status_code=400, detail="Invoice not ready to close")
    _set_status(inv, "closed")
    inv.closed_at = datetime.now(timezone.utc)
    inv.closed_by_id = user.id
    db.commit()
    return _inv_resp(_get_invoice(db, invoice_id, company.id))


@router.post("/{invoice_id}/reminder", response_model=InvoiceResponse)
def reminder(invoice_id: int, request: Request, user: User = Depends(require_permission("invoices.send")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    inv = _get_invoice(db, invoice_id, company.id)
    if _float(inv.outstanding_amount) <= 0 or not inv.client_email or not inv.share_token:
        raise HTTPException(status_code=400, detail="Cannot send reminder")
    share_url = f"{FRONTEND_URL}/invoice/{inv.share_token}"
    try:
        from services.email_service import render_template, send_email
        html = render_template("invoice_sent.html", company_name=company.display_name, invoice_number=inv.invoice_number,
                               client_name=inv.client_name, grand_total=f"{inv.currency} {_float(inv.outstanding_amount):,.2f} due",
                               due_date=inv.due_date.strftime("%d %b %Y") if inv.due_date else "TBD", share_url=share_url,
                               message="Payment reminder for your outstanding invoice.")
        send_email(inv.client_email, f"Payment reminder: {inv.invoice_number}", html)
    except Exception:
        pass
    return _inv_resp(inv)


# Public


@public_router.get("/{token}", response_model=InvoicePublicResponse)
def public_view(token: str, db: Session = Depends(get_db)):
    inv = _get_by_token(db, token)
    if inv.viewed_at is None and inv.status == "sent":
        inv.status = "viewed"
        inv.viewed_at = datetime.now(timezone.utc)
        db.commit()
        inv = _get_by_token(db, token)
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == inv.company_id).first()
    _check_overdue(inv)
    db.commit()
    return InvoicePublicResponse(invoice=_inv_resp(inv), company=_branding(inv.company, settings), is_overdue=_is_overdue(inv))


@public_router.post("/{token}/view", response_model=InvoicePublicResponse)
def public_mark_viewed(token: str, db: Session = Depends(get_db)):
    inv = _get_by_token(db, token)
    if inv.status == "sent":
        inv.status = "viewed"
    inv.viewed_at = datetime.now(timezone.utc)
    db.commit()
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == inv.company_id).first()
    return InvoicePublicResponse(invoice=_inv_resp(_get_by_token(db, token)), company=_branding(inv.company, settings), is_overdue=_is_overdue(inv))
