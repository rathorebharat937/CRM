from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import (
    Company,
    Contact,
    Deal,
    Expense,
    PurchaseOrder,
    PurchaseOrderBilling,
    PurchaseOrderLineItem,
    User,
    VendorBill,
    VendorBillAttachment,
    VendorBillLineItem,
    VendorBillPayment,
)
from permissions import role_has_permission
from purchase_order_config import BILLING_STATUSES
from routers.purchase_orders_router import _rollup_fulfillment, _sync_fulfillment_status
from schemas import (
    VendorBillAttachmentResponse,
    VendorBillCancelRequest,
    VendorBillCreateRequest,
    VendorBillLineItemFields,
    VendorBillLineItemResponse,
    VendorBillListResponse,
    VendorBillPaymentFields,
    VendorBillPaymentMethodOption,
    VendorBillPaymentResponse,
    VendorBillRejectRequest,
    VendorBillResponse,
    VendorBillReviewRequest,
    VendorBillStatsResponse,
    VendorBillStatusOption,
    VendorBillUpdateRequest,
)
from vendor_bills_config import (
    ALLOWED_TRANSITIONS,
    APPROVAL_THRESHOLD,
    DEFAULT_PAYMENT_TERMS,
    EDITABLE_STATUSES,
    PAYABLE_STATUSES,
    PAYMENT_METHOD_LABELS,
    PAYMENT_METHODS,
    VENDOR_BILL_STATUS_LABELS,
    VENDOR_BILL_STATUSES,
)

router = APIRouter(prefix="/vendor-bills", tags=["vendor-bills"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads" / "vendor_bills"
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
MAX_FILE_SIZE = 10 * 1024 * 1024




def _decimal(v) -> Decimal:
    return Decimal("0") if v is None else Decimal(str(v))


def _float(v) -> float:
    return 0.0 if v is None else float(v)


def _validate_status(status: str) -> None:
    if status not in VENDOR_BILL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(VENDOR_BILL_STATUSES)}")


def _validate_payment_method(method: str) -> None:
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Payment method must be one of: {', '.join(PAYMENT_METHODS)}")


def _set_status(bill: VendorBill, new_status: str) -> None:
    _validate_status(new_status)
    allowed = ALLOWED_TRANSITIONS.get(bill.status, set())
    if new_status not in allowed and bill.status != new_status:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {bill.status} to {new_status}")
    bill.status = new_status


def _generate_bill_number(db: Session, company: Company) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"VB-{year}-"
    last = (
        db.query(VendorBill)
        .filter(VendorBill.company_id == company.id, VendorBill.bill_number.like(f"{prefix}%"))
        .order_by(VendorBill.id.desc())
        .first()
    )
    seq = 1
    if last and last.bill_number:
        try:
            seq = int(last.bill_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _compute_line_totals(item: VendorBillLineItemFields) -> dict:
    qty = _decimal(item.quantity)
    price = _decimal(item.unit_price)
    tr = _decimal(item.tax_rate)
    subtotal = qty * price
    tax = subtotal * (tr / Decimal("100"))
    return {"line_subtotal": subtotal, "line_total": subtotal + tax, "line_tax": tax}


def _compute_bill_totals(items: list[VendorBillLineItemFields], round_off: float = 0) -> dict:
    subtotal = Decimal("0")
    total_tax = Decimal("0")
    for item in items:
        totals = _compute_line_totals(item)
        subtotal += totals["line_subtotal"]
        total_tax += totals["line_tax"]
    ro = _decimal(round_off)
    grand = subtotal + total_tax + ro
    return {"subtotal": subtotal, "total_tax": total_tax, "round_off": ro, "grand_total": grand}


def _line_pending_billing(item: PurchaseOrderLineItem) -> float:
    return max(_float(item.received_quantity) - _float(item.billed_quantity), 0.0)


def _validate_po_line_quantities(bill: VendorBill, po: PurchaseOrder | None, reverse: bool = False) -> None:
    if not po:
        return
    po_lines = {li.id: li for li in po.line_items}
    for line in bill.line_items:
        if not line.purchase_order_line_item_id:
            continue
        po_line = po_lines.get(line.purchase_order_line_item_id)
        if not po_line:
            raise HTTPException(status_code=400, detail="Invalid PO line reference on bill")
        qty = _float(line.quantity)
        if reverse:
            continue
        pending = _line_pending_billing(po_line)
        if qty > pending + 0.001:
            raise HTTPException(
                status_code=400,
                detail=f"Billed quantity ({qty}) exceeds pending billable quantity ({pending}) for line: {po_line.description}",
            )


def _apply_po_billing(bill: VendorBill, po: PurchaseOrder, user: User, reverse: bool = False) -> None:
    sign = Decimal("-1") if reverse else Decimal("1")
    for line in bill.line_items:
        if not line.purchase_order_line_item_id:
            continue
        po_line = next((li for li in po.line_items if li.id == line.purchase_order_line_item_id), None)
        if not po_line:
            continue
        qty_delta = _decimal(line.quantity) * sign
        amount_delta = _decimal(line.line_total) * sign
        po_line.billed_quantity = _decimal(po_line.billed_quantity) + qty_delta
        po_line.billed_amount = _decimal(po_line.billed_amount) + amount_delta
        if not reverse:
            po.billings.append(
                PurchaseOrderBilling(
                    line_item_id=po_line.id,
                    recorded_by_id=user.id,
                    quantity=_decimal(line.quantity),
                    amount=_decimal(line.line_total),
                    bill_reference=bill.bill_number or bill.supplier_invoice_number,
                    notes=f"Vendor bill {bill.bill_number or bill.id}",
                )
            )
    _rollup_fulfillment(po)
    _sync_fulfillment_status(po)


def _apply_lines(bill: VendorBill, items: list[VendorBillLineItemFields]) -> None:
    bill.line_items.clear()
    for idx, item in enumerate(items):
        totals = _compute_line_totals(item)
        bill.line_items.append(
            VendorBillLineItem(
                purchase_order_line_item_id=item.purchase_order_line_item_id,
                sort_order=item.sort_order if item.sort_order else idx,
                description=item.description.strip(),
                unit=item.unit or "Unit",
                quantity=item.quantity,
                unit_price=item.unit_price,
                tax_rate=item.tax_rate,
                line_subtotal=totals["line_subtotal"],
                line_total=totals["line_total"],
            )
        )


def _sync_balances(bill: VendorBill) -> None:
    paid = sum(_decimal(p.amount) for p in bill.payments)
    bill.amount_paid = paid
    bill.outstanding_amount = max(_decimal(bill.grand_total) - paid, Decimal("0"))
    if _float(bill.outstanding_amount) <= 0 and bill.status in PAYABLE_STATUSES | {"partially_paid"}:
        bill.status = "paid"
    elif paid > 0 and bill.status in {"approved", "overdue"}:
        bill.status = "partially_paid"
    _check_overdue(bill)


def _is_overdue(bill: VendorBill) -> bool:
    if not bill.due_date or _float(bill.outstanding_amount) <= 0:
        return False
    due = bill.due_date if bill.due_date.tzinfo else bill.due_date.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > due and bill.status in PAYABLE_STATUSES | {"partially_paid", "overdue"}


def _check_overdue(bill: VendorBill) -> None:
    if _is_overdue(bill) and bill.status in {"approved", "partially_paid"}:
        bill.status = "overdue"


def _line_resp(li: VendorBillLineItem) -> VendorBillLineItemResponse:
    po_line = li.purchase_order_line_item
    return VendorBillLineItemResponse(
        id=li.id,
        purchase_order_line_item_id=li.purchase_order_line_item_id,
        sort_order=li.sort_order,
        description=li.description,
        unit=li.unit,
        quantity=_float(li.quantity),
        unit_price=_float(li.unit_price),
        tax_rate=_float(li.tax_rate),
        line_subtotal=_float(li.line_subtotal),
        line_total=_float(li.line_total),
        po_ordered_quantity=_float(po_line.ordered_quantity) if po_line else None,
        po_received_quantity=_float(po_line.received_quantity) if po_line else None,
        po_billed_quantity=_float(po_line.billed_quantity) if po_line else None,
        po_pending_billing_quantity=_line_pending_billing(po_line) if po_line else None,
    )


def _pay_resp(p: VendorBillPayment) -> VendorBillPaymentResponse:
    return VendorBillPaymentResponse(
        id=p.id,
        amount=_float(p.amount),
        payment_date=p.payment_date,
        payment_method=p.payment_method,
        reference=p.reference,
        note=p.note,
        recorded_by_id=p.recorded_by_id,
        recorded_by_name=p.recorded_by.name if p.recorded_by else None,
        created_at=p.created_at,
    )


def _bill_resp(bill: VendorBill) -> VendorBillResponse:
    _check_overdue(bill)
    return VendorBillResponse(
        id=bill.id,
        bill_number=bill.bill_number,
        supplier_invoice_number=bill.supplier_invoice_number,
        title=bill.title,
        status=bill.status,
        currency=bill.currency,
        bill_date=bill.bill_date,
        due_date=bill.due_date,
        payment_terms=bill.payment_terms,
        purchase_order_id=bill.purchase_order_id,
        po_number=bill.purchase_order.po_number if bill.purchase_order else None,
        vendor_name=bill.vendor_name,
        vendor_email=bill.vendor_email,
        vendor_phone=bill.vendor_phone,
        vendor_gstin=bill.vendor_gstin,
        vendor_address=bill.vendor_address,
        deal_id=bill.deal_id,
        deal_title=bill.deal.title if bill.deal else None,
        contact_id=bill.contact_id,
        contact_name=bill.contact.name if bill.contact else None,
        expense_id=bill.expense_id,
        subtotal=_float(bill.subtotal),
        total_tax=_float(bill.total_tax),
        round_off=_float(bill.round_off),
        grand_total=_float(bill.grand_total),
        amount_paid=_float(bill.amount_paid),
        outstanding_amount=_float(bill.outstanding_amount),
        internal_notes=bill.internal_notes,
        approval_notes=bill.approval_notes,
        rejection_reason=bill.rejection_reason,
        cancellation_reason=bill.cancellation_reason,
        created_by_id=bill.created_by_id,
        created_by_name=bill.created_by.name if bill.created_by else None,
        reviewed_by_name=bill.reviewed_by.name if bill.reviewed_by else None,
        approved_by_name=bill.approved_by.name if bill.approved_by else None,
        submitted_at=bill.submitted_at,
        reviewed_at=bill.reviewed_at,
        approved_at=bill.approved_at,
        cancelled_at=bill.cancelled_at,
        closed_at=bill.closed_at,
        last_payment_at=bill.last_payment_at,
        created_at=bill.created_at,
        updated_at=bill.updated_at,
        line_items=[_line_resp(li) for li in bill.line_items],
        payments=[_pay_resp(p) for p in bill.payments],
        attachments=[
            VendorBillAttachmentResponse(
                id=a.id,
                original_filename=a.original_filename,
                content_type=a.content_type,
                file_size=a.file_size,
                uploaded_by_name=a.uploaded_by.name if a.uploaded_by else None,
                created_at=a.created_at,
            )
            for a in bill.attachments
        ],
        is_overdue=_is_overdue(bill),
    )


def _get_bill(db: Session, bill_id: int, company_id: int) -> VendorBill:
    bill = (
        db.query(VendorBill)
        .options(
            joinedload(VendorBill.created_by),
            joinedload(VendorBill.reviewed_by),
            joinedload(VendorBill.approved_by),
            joinedload(VendorBill.purchase_order),
            joinedload(VendorBill.deal),
            joinedload(VendorBill.contact),
            joinedload(VendorBill.line_items).joinedload(VendorBillLineItem.purchase_order_line_item),
            joinedload(VendorBill.payments).joinedload(VendorBillPayment.recorded_by),
            joinedload(VendorBill.attachments).joinedload(VendorBillAttachment.uploaded_by),
        )
        .filter(VendorBill.id == bill_id, VendorBill.company_id == company_id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Vendor bill not found")
    return bill


def _get_po(db: Session, po_id: int, company_id: int) -> PurchaseOrder:
    po = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.line_items))
        .filter(PurchaseOrder.id == po_id, PurchaseOrder.company_id == company_id)
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


def _validate_refs(db: Session, company: Company, payload: VendorBillCreateRequest) -> PurchaseOrder | None:
    po = None
    if payload.purchase_order_id:
        po = _get_po(db, payload.purchase_order_id, company.id)
    if payload.deal_id:
        if not db.query(Deal).filter(Deal.id == payload.deal_id, Deal.company_id == company.id).first():
            raise HTTPException(status_code=404, detail="Deal not found")
    if payload.contact_id:
        if not db.query(Contact).filter(Contact.id == payload.contact_id, Contact.company_id == company.id).first():
            raise HTTPException(status_code=404, detail="Contact not found")
    if payload.expense_id:
        if not db.query(Expense).filter(Expense.id == payload.expense_id, Expense.company_id == company.id).first():
            raise HTTPException(status_code=404, detail="Expense not found")
    if payload.due_date and payload.bill_date and payload.due_date < payload.bill_date:
        raise HTTPException(status_code=400, detail="Due date cannot precede bill date")
    return po


def _build_bill(db: Session, company: Company, payload: VendorBillCreateRequest, user: User) -> VendorBill:
    po = _validate_refs(db, company, payload)
    totals = _compute_bill_totals(payload.line_items, payload.round_off)
    bill = VendorBill(
        company_id=company.id,
        created_by_id=user.id,
        title=payload.title.strip(),
        supplier_invoice_number=payload.supplier_invoice_number,
        status="draft",
        currency=payload.currency or company.currency,
        bill_date=payload.bill_date,
        due_date=payload.due_date,
        payment_terms=payload.payment_terms or DEFAULT_PAYMENT_TERMS,
        purchase_order_id=payload.purchase_order_id,
        vendor_name=payload.vendor_name.strip(),
        vendor_email=payload.vendor_email,
        vendor_phone=payload.vendor_phone,
        vendor_gstin=payload.vendor_gstin,
        vendor_address=payload.vendor_address,
        deal_id=payload.deal_id,
        contact_id=payload.contact_id,
        expense_id=payload.expense_id,
        subtotal=totals["subtotal"],
        total_tax=totals["total_tax"],
        round_off=totals["round_off"],
        grand_total=totals["grand_total"],
        outstanding_amount=totals["grand_total"],
        amount_paid=Decimal("0"),
        internal_notes=payload.internal_notes,
    )
    db.add(bill)
    db.flush()
    _apply_lines(bill, payload.line_items)
    if po:
        _validate_po_line_quantities(bill, po)
    return bill


def _can_edit(bill: VendorBill, user: User, db: Session) -> bool:
    if role_has_permission(db, user.role, "vendor_bills.edit_all"):
        return bill.status in EDITABLE_STATUSES
    if role_has_permission(db, user.role, "vendor_bills.edit_own") and bill.created_by_id == user.id:
        return bill.status in EDITABLE_STATUSES
    return False


@router.get("/statuses", response_model=list[VendorBillStatusOption])
def statuses(_: User = Depends(require_permission("vendor_bills.view"))):
    return [VendorBillStatusOption(value=s, label=VENDOR_BILL_STATUS_LABELS[s]) for s in VENDOR_BILL_STATUSES]


@router.get("/payment-methods", response_model=list[VendorBillPaymentMethodOption])
def payment_methods(_: User = Depends(require_permission("vendor_bills.view"))):
    return [VendorBillPaymentMethodOption(value=m, label=PAYMENT_METHOD_LABELS[m]) for m in PAYMENT_METHODS]


@router.get("/stats/summary", response_model=VendorBillStatsResponse)
def stats(user: User = Depends(require_permission("vendor_bills.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    now = datetime.now(timezone.utc)
    week_end = now + timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    bills = db.query(VendorBill).filter(VendorBill.company_id == company.id).all()
    outstanding = overdue = due_week = paid_month = pending_count = pending_amount = 0.0
    vendor_totals: dict[str, float] = {}
    vendor_contact_ids: dict[str, int | None] = {}
    aging = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}

    for bill in bills:
        out = _float(bill.outstanding_amount)
        if bill.status in {"submitted", "under_review"}:
            pending_count += 1
            pending_amount += _float(bill.grand_total)
        if bill.status in PAYABLE_STATUSES | {"partially_paid", "overdue"} and out > 0:
            outstanding += out
            vendor_totals[bill.vendor_name] = vendor_totals.get(bill.vendor_name, 0) + out
            if bill.contact_id and bill.vendor_name not in vendor_contact_ids:
                vendor_contact_ids[bill.vendor_name] = bill.contact_id
            elif bill.vendor_name not in vendor_contact_ids:
                vendor_contact_ids[bill.vendor_name] = None
            if bill.due_date:
                due = bill.due_date if bill.due_date.tzinfo else bill.due_date.replace(tzinfo=timezone.utc)
                days = (now - due).days
                if days <= 0:
                    aging["current"] += out
                    if due <= week_end:
                        due_week += out
                elif days <= 30:
                    aging["1_30"] += out
                    overdue += out
                elif days <= 60:
                    aging["31_60"] += out
                    overdue += out
                elif days <= 90:
                    aging["61_90"] += out
                    overdue += out
                else:
                    aging["90_plus"] += out
                    overdue += out
        if bill.status == "paid" and bill.last_payment_at and bill.last_payment_at >= month_start:
            paid_month += _float(bill.grand_total)

    return VendorBillStatsResponse(
        total_outstanding=outstanding,
        overdue_amount=overdue,
        due_this_week_amount=due_week,
        pending_approval_count=pending_count,
        pending_approval_amount=pending_amount,
        paid_this_month=paid_month,
        by_vendor=[
            {"name": k, "value": v, "contact_id": vendor_contact_ids.get(k)}
            for k, v in sorted(vendor_totals.items(), key=lambda x: x[1], reverse=True)[:10]
        ],
        aging_buckets=[
            {"name": "Current", "value": aging["current"]},
            {"name": "1-30 days", "value": aging["1_30"]},
            {"name": "31-60 days", "value": aging["31_60"]},
            {"name": "61-90 days", "value": aging["61_90"]},
            {"name": "90+ days", "value": aging["90_plus"]},
        ],
    )


@router.get("/approval-queue", response_model=VendorBillListResponse)
def approval_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("vendor_bills.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(VendorBill)
        .options(
            joinedload(VendorBill.created_by),
            joinedload(VendorBill.purchase_order),
            joinedload(VendorBill.line_items),
            joinedload(VendorBill.payments),
            joinedload(VendorBill.attachments),
        )
        .filter(VendorBill.company_id == company.id, VendorBill.status.in_(["submitted", "under_review"]))
    )
    total = query.count()
    items = query.order_by(VendorBill.submitted_at.asc().nullslast()).offset((page - 1) * limit).limit(limit).all()
    return VendorBillListResponse(items=[_bill_resp(b) for b in items], total=total, page=page, limit=limit)


@router.get("", response_model=VendorBillListResponse)
def list_bills(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    payment_status: str | None = None,
    po_linked: bool | None = None,
    purchase_order_id: int | None = None,
    mine: bool = False,
    search: str | None = None,
    user: User = Depends(require_permission("vendor_bills.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(VendorBill)
        .options(
            joinedload(VendorBill.created_by),
            joinedload(VendorBill.purchase_order),
            joinedload(VendorBill.line_items),
            joinedload(VendorBill.payments),
            joinedload(VendorBill.attachments),
        )
        .filter(VendorBill.company_id == company.id)
    )
    if mine:
        query = query.filter(VendorBill.created_by_id == user.id)
    if status:
        _validate_status(status)
        query = query.filter(VendorBill.status == status)
    if payment_status == "unpaid":
        query = query.filter(VendorBill.status.in_(list(PAYABLE_STATUSES)), VendorBill.outstanding_amount > 0)
    elif payment_status == "partial":
        query = query.filter(VendorBill.status == "partially_paid")
    elif payment_status == "paid":
        query = query.filter(VendorBill.status == "paid")
    elif payment_status == "overdue":
        query = query.filter(VendorBill.status == "overdue")
    if po_linked is True:
        query = query.filter(VendorBill.purchase_order_id.isnot(None))
    elif po_linked is False:
        query = query.filter(VendorBill.purchase_order_id.is_(None))
    if purchase_order_id:
        query = query.filter(VendorBill.purchase_order_id == purchase_order_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            VendorBill.title.ilike(term),
            VendorBill.vendor_name.ilike(term),
            VendorBill.bill_number.ilike(term),
            VendorBill.supplier_invoice_number.ilike(term),
        ))
    total = query.count()
    items = query.order_by(VendorBill.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return VendorBillListResponse(items=[_bill_resp(b) for b in items], total=total, page=page, limit=limit)


@router.post("/from-purchase-order/{po_id}", response_model=VendorBillResponse, status_code=201)
def create_from_po(
    po_id: int,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status not in BILLING_STATUSES:
        raise HTTPException(status_code=400, detail="PO must be received before creating a vendor bill")

    line_items = []
    for li in po.line_items:
        pending = _line_pending_billing(li)
        if pending <= 0:
            continue
        line_items.append(
            VendorBillLineItemFields(
                purchase_order_line_item_id=li.id,
                sort_order=li.sort_order,
                description=li.description,
                quantity=pending,
                unit=li.unit or "Unit",
                unit_price=_float(li.unit_price),
                tax_rate=_float(li.tax_rate),
            )
        )
    if not line_items:
        raise HTTPException(status_code=400, detail="No billable quantity remaining on this PO")

    due = datetime.now(timezone.utc) + timedelta(days=30)
    payload = VendorBillCreateRequest(
        title=f"Vendor Bill — {po.title}",
        bill_date=datetime.now(timezone.utc),
        due_date=due,
        payment_terms=po.payment_terms or DEFAULT_PAYMENT_TERMS,
        purchase_order_id=po.id,
        vendor_name=po.vendor_name,
        vendor_email=po.vendor_email,
        vendor_phone=po.vendor_phone,
        deal_id=po.deal_id,
        contact_id=po.contact_id,
        internal_notes=f"Generated from PO {po.po_number}",
        line_items=line_items,
    )
    bill = _build_bill(db, company, payload, user)
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    log_activity(db, "vendor_bill_created_from_po", user_id=user.id, email=user.email, details=bill.title, ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.post("", response_model=VendorBillResponse, status_code=201)
def create_bill(
    payload: VendorBillCreateRequest,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _build_bill(db, company, payload, user)
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    log_activity(db, "vendor_bill_created", user_id=user.id, email=user.email, details=bill.title, ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.get("/{bill_id}", response_model=VendorBillResponse)
def get_bill(bill_id: int, user: User = Depends(require_permission("vendor_bills.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    return _bill_resp(_get_bill(db, bill_id, company.id))


@router.put("/{bill_id}", response_model=VendorBillResponse)
def update_bill(
    bill_id: int,
    payload: VendorBillUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.edit_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if not _can_edit(bill, user, db):
        raise HTTPException(status_code=403, detail="Not allowed to edit this bill")
    po = _validate_refs(db, company, payload)
    totals = _compute_bill_totals(payload.line_items, payload.round_off)
    bill.title = payload.title.strip()
    bill.supplier_invoice_number = payload.supplier_invoice_number
    bill.currency = payload.currency
    bill.bill_date = payload.bill_date
    bill.due_date = payload.due_date
    bill.payment_terms = payload.payment_terms or DEFAULT_PAYMENT_TERMS
    bill.purchase_order_id = payload.purchase_order_id
    bill.vendor_name = payload.vendor_name.strip()
    bill.vendor_email = payload.vendor_email
    bill.vendor_phone = payload.vendor_phone
    bill.vendor_gstin = payload.vendor_gstin
    bill.vendor_address = payload.vendor_address
    bill.deal_id = payload.deal_id
    bill.contact_id = payload.contact_id
    bill.expense_id = payload.expense_id
    bill.internal_notes = payload.internal_notes
    bill.subtotal = totals["subtotal"]
    bill.total_tax = totals["total_tax"]
    bill.round_off = totals["round_off"]
    bill.grand_total = totals["grand_total"]
    bill.outstanding_amount = totals["grand_total"] - _decimal(bill.amount_paid)
    _apply_lines(bill, payload.line_items)
    if po:
        _validate_po_line_quantities(bill, po)
    if bill.status == "rejected":
        bill.rejection_reason = None
        bill.approval_notes = None
        bill.status = "draft"
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    log_activity(db, "vendor_bill_updated", user_id=user.id, email=user.email, details=bill.title, ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.delete("/{bill_id}")
def delete_bill(
    bill_id: int,
    user: User = Depends(require_permission("vendor_bills.delete")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft bills can be deleted")
    if not _can_edit(bill, user, db):
        raise HTTPException(status_code=403, detail="Not allowed to delete this bill")
    db.delete(bill)
    db.commit()
    return {"ok": True}


@router.post("/{bill_id}/submit", response_model=VendorBillResponse)
def submit_bill(
    bill_id: int,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.submit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if bill.created_by_id != user.id and not role_has_permission(db, user.role, "vendor_bills.edit_all"):
        raise HTTPException(status_code=403, detail="Only the creator can submit this bill")
    if bill.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected bills can be submitted")
    if not bill.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    po = bill.purchase_order
    if po:
        po = _get_po(db, po.id, company.id)
        _validate_po_line_quantities(bill, po)
    if not bill.bill_number:
        bill.bill_number = _generate_bill_number(db, company)
    bill.submitted_at = datetime.now(timezone.utc)
    _set_status(bill, "submitted")
    if _float(bill.grand_total) >= APPROVAL_THRESHOLD:
        _set_status(bill, "under_review")
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    log_activity(db, "vendor_bill_submitted", user_id=user.id, email=user.email, details=bill.bill_number, ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.post("/{bill_id}/approve", response_model=VendorBillResponse)
def approve_bill(
    bill_id: int,
    payload: VendorBillReviewRequest,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=400, detail="Bill is not pending approval")
    po = None
    if bill.purchase_order_id:
        po = _get_po(db, bill.purchase_order_id, company.id)
        _validate_po_line_quantities(bill, po)
    bill.reviewed_by_id = user.id
    bill.approved_by_id = user.id
    bill.reviewed_at = datetime.now(timezone.utc)
    bill.approved_at = datetime.now(timezone.utc)
    bill.approval_notes = payload.comments
    _set_status(bill, "approved")
    if po:
        _apply_po_billing(bill, po, user)
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    log_activity(db, "vendor_bill_approved", user_id=user.id, email=user.email, details=bill.bill_number, ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.post("/{bill_id}/reject", response_model=VendorBillResponse)
def reject_bill(
    bill_id: int,
    payload: VendorBillRejectRequest,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.reject")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=400, detail="Bill is not pending approval")
    bill.reviewed_by_id = user.id
    bill.reviewed_at = datetime.now(timezone.utc)
    bill.rejection_reason = payload.reason.strip()
    bill.approval_notes = payload.comments
    _set_status(bill, "rejected")
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    log_activity(db, "vendor_bill_rejected", user_id=user.id, email=user.email, details=bill.bill_number, ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.post("/{bill_id}/record-payment", response_model=VendorBillResponse)
def record_payment(
    bill_id: int,
    payload: VendorBillPaymentFields,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.record_payment")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status not in PAYABLE_STATUSES | {"partially_paid", "overdue"}:
        raise HTTPException(status_code=400, detail="Cannot record payment on this bill")
    _validate_payment_method(payload.payment_method)
    if _decimal(payload.amount) > _decimal(bill.outstanding_amount):
        raise HTTPException(status_code=400, detail="Payment exceeds outstanding balance")
    bill.payments.append(
        VendorBillPayment(
            amount=_decimal(payload.amount),
            payment_date=payload.payment_date,
            payment_method=payload.payment_method,
            reference=payload.reference,
            note=payload.note,
            recorded_by_id=user.id,
        )
    )
    bill.last_payment_at = datetime.now(timezone.utc)
    _sync_balances(bill)
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    action = "vendor_bill_paid" if bill.status == "paid" else "vendor_bill_payment_recorded"
    log_activity(db, action, user_id=user.id, email=user.email, details=f"Payment {_float(payload.amount)} on {bill.bill_number}", ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.post("/{bill_id}/close", response_model=VendorBillResponse)
def close_bill(
    bill_id: int,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.record_payment")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status != "paid":
        raise HTTPException(status_code=400, detail="Only paid bills can be closed")
    bill.closed_at = datetime.now(timezone.utc)
    _set_status(bill, "closed")
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    log_activity(db, "vendor_bill_closed", user_id=user.id, email=user.email, details=bill.bill_number, ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.post("/{bill_id}/cancel", response_model=VendorBillResponse)
def cancel_bill(
    bill_id: int,
    payload: VendorBillCancelRequest,
    request: Request,
    user: User = Depends(require_permission("vendor_bills.cancel")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status in {"paid", "closed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Bill cannot be cancelled")
    was_approved = bill.status in PAYABLE_STATUSES | {"partially_paid", "overdue", "approved"}
    po = None
    if was_approved and bill.purchase_order_id:
        po = _get_po(db, bill.purchase_order_id, company.id)
        _apply_po_billing(bill, po, user, reverse=True)
    bill.cancellation_reason = payload.reason.strip()
    bill.cancelled_at = datetime.now(timezone.utc)
    _set_status(bill, "cancelled")
    db.commit()
    bill = _get_bill(db, bill.id, company.id)
    log_activity(db, "vendor_bill_cancelled", user_id=user.id, email=user.email, details=bill.bill_number, ip_address=get_client_ip(request))
    return _bill_resp(bill)


@router.post("/{bill_id}/attachments", response_model=VendorBillAttachmentResponse)
async def upload_attachment(
    bill_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("vendor_bills.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    if bill.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot add attachment to a non-editable bill")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="File type must be JPG, PNG, WEBP, or PDF")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size must be under 10MB")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "invoice").suffix or ".bin"
    stored = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_ROOT / stored
    path.write_bytes(data)

    attachment = VendorBillAttachment(
        vendor_bill_id=bill.id,
        uploaded_by_id=user.id,
        original_filename=file.filename or stored,
        stored_filename=stored,
        content_type=content_type,
        file_size=len(data),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    log_activity(db, "vendor_bill_attachment_uploaded", user_id=user.id, email=user.email, details=attachment.original_filename, ip_address=get_client_ip(request))
    return VendorBillAttachmentResponse(
        id=attachment.id,
        original_filename=attachment.original_filename,
        content_type=attachment.content_type,
        file_size=attachment.file_size,
        uploaded_by_name=user.name,
        created_at=attachment.created_at,
    )


@router.get("/{bill_id}/attachments/{attachment_id}/download")
def download_attachment(
    bill_id: int,
    attachment_id: int,
    user: User = Depends(require_permission("vendor_bills.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    bill = _get_bill(db, bill_id, company.id)
    attachment = next((a for a in bill.attachments if a.id == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = UPLOAD_ROOT / attachment.stored_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(path, filename=attachment.original_filename, media_type=attachment.content_type or "application/octet-stream")
