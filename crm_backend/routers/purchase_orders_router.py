from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import (
    Company,
    Contact,
    Deal,
    Product,
    PurchaseOrder,
    PurchaseOrderAttachment,
    PurchaseOrderBilling,
    PurchaseOrderLineItem,
    PurchaseOrderReceipt,
    User,
)
from permissions import role_has_permission
from services.quality_service import create_incoming_po_inspection
from purchase_order_config import (
    ALLOWED_TRANSITIONS,
    APPROVAL_THRESHOLD,
    BILLING_STATUSES,
    DEFAULT_PO_PREFIX,
    EDITABLE_STATUSES,
    PAYMENT_TERM_LABELS,
    PAYMENT_TERMS,
    PO_STATUS_LABELS,
    PO_STATUSES,
    RECEIPT_STATUSES,
)
from schemas import (
    PurchaseOrderAttachmentResponse,
    PurchaseOrderBillingResponse,
    PurchaseOrderCreateRequest,
    PurchaseOrderLineItemFields,
    PurchaseOrderListResponse,
    PurchaseOrderPaymentTermOption,
    PurchaseOrderRecordBillingRequest,
    PurchaseOrderRecordReceiptRequest,
    PurchaseOrderRejectRequest,
    PurchaseOrderResponse,
    PurchaseOrderReviewRequest,
    PurchaseOrderStatsResponse,
    PurchaseOrderStatusOption,
    PurchaseOrderUpdateRequest,
)

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads" / "purchase_orders"
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
MAX_FILE_SIZE = 5 * 1024 * 1024




def _decimal(value: float | Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _float(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _validate_status(status: str) -> None:
    if status not in PO_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(PO_STATUSES)}")


def _validate_payment_terms(terms: str | None) -> None:
    if terms and terms not in PAYMENT_TERMS:
        raise HTTPException(status_code=400, detail=f"Payment terms must be one of: {', '.join(PAYMENT_TERMS)}")


def _set_status(po: PurchaseOrder, new_status: str) -> None:
    _validate_status(new_status)
    allowed = ALLOWED_TRANSITIONS.get(po.status, set())
    if new_status not in allowed and po.status != new_status:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {po.status} to {new_status}")
    po.status = new_status


def _generate_po_number(db: Session, company: Company) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"{DEFAULT_PO_PREFIX}{year}-"
    last = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.company_id == company.id, PurchaseOrder.po_number.like(f"{prefix}%"))
        .order_by(PurchaseOrder.id.desc())
        .first()
    )
    seq = 1
    if last and last.po_number:
        try:
            seq = int(last.po_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _compute_line_totals(item: PurchaseOrderLineItemFields | PurchaseOrderLineItem) -> dict[str, Decimal]:
    qty = _decimal(item.ordered_quantity if hasattr(item, "ordered_quantity") else item["ordered_quantity"])
    unit_price = _decimal(item.unit_price if hasattr(item, "unit_price") else item["unit_price"])
    tax_rate = _decimal(item.tax_rate if hasattr(item, "tax_rate") else item["tax_rate"])
    line_subtotal = qty * unit_price
    line_tax = line_subtotal * (tax_rate / Decimal("100"))
    line_total = line_subtotal + line_tax
    return {"line_subtotal": line_subtotal, "line_total": line_total, "line_tax": line_tax}


def _compute_po_totals(line_items: list[PurchaseOrderLineItem]) -> dict[str, Decimal]:
    subtotal = Decimal("0")
    total_tax = Decimal("0")
    for item in line_items:
        totals = _compute_line_totals(item)
        subtotal += totals["line_subtotal"]
        total_tax += totals["line_tax"]
    return {"subtotal": subtotal, "total_tax": total_tax, "grand_total": subtotal + total_tax}


def _line_pending_receipt(item: PurchaseOrderLineItem) -> float:
    return max(_float(item.ordered_quantity) - _float(item.received_quantity), 0.0)


def _line_pending_billing(item: PurchaseOrderLineItem) -> float:
    return max(_float(item.received_quantity) - _float(item.billed_quantity), 0.0)


def _line_received_value(item: PurchaseOrderLineItem) -> Decimal:
    if _float(item.ordered_quantity) <= 0:
        return Decimal("0")
    ratio = _decimal(item.received_quantity) / _decimal(item.ordered_quantity)
    return _decimal(item.line_total) * ratio


def _line_pending_receipt_value(item: PurchaseOrderLineItem) -> Decimal:
    return max(_decimal(item.line_total) - _line_received_value(item), Decimal("0"))


def _line_pending_billing_value(item: PurchaseOrderLineItem) -> Decimal:
    if _float(item.received_quantity) <= 0:
        return Decimal("0")
    received_val = _line_received_value(item)
    return max(received_val - _decimal(item.billed_amount), Decimal("0"))


def _rollup_fulfillment(po: PurchaseOrder) -> None:
    received_value = Decimal("0")
    billed_value = Decimal("0")
    for item in po.line_items:
        received_value += _line_received_value(item)
        billed_value += _decimal(item.billed_amount)
    po.received_value = received_value
    po.billed_value = billed_value


def _all_lines_fully_received(po: PurchaseOrder) -> bool:
    return all(_float(li.received_quantity) >= _float(li.ordered_quantity) for li in po.line_items)


def _any_line_received(po: PurchaseOrder) -> bool:
    return any(_float(li.received_quantity) > 0 for li in po.line_items)


def _all_lines_fully_billed(po: PurchaseOrder) -> bool:
    return all(_float(li.billed_quantity) >= _float(li.received_quantity) and _float(li.received_quantity) > 0 for li in po.line_items)


def _any_line_billed(po: PurchaseOrder) -> bool:
    return any(_float(li.billed_quantity) > 0 for li in po.line_items)


def _sync_fulfillment_status(po: PurchaseOrder) -> None:
    if po.status in {"draft", "submitted", "under_review", "approved", "rejected", "cancelled", "closed"}:
        return
    if _all_lines_fully_billed(po) and _all_lines_fully_received(po):
        po.status = "fully_billed"
    elif _any_line_billed(po):
        po.status = "partially_billed"
    elif _all_lines_fully_received(po):
        po.status = "fully_received"
    elif _any_line_received(po):
        po.status = "partially_received"


def _apply_line_items(po: PurchaseOrder, items: list[PurchaseOrderLineItemFields]) -> None:
    if not items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    po.line_items.clear()
    for idx, item in enumerate(items):
        totals = _compute_line_totals(item)
        po.line_items.append(
            PurchaseOrderLineItem(
                product_id=item.product_id,
                sort_order=item.sort_order if item.sort_order else idx,
                description=item.description.strip(),
                sku=item.sku,
                unit=item.unit,
                ordered_quantity=item.ordered_quantity,
                unit_price=item.unit_price,
                tax_rate=item.tax_rate,
                line_subtotal=totals["line_subtotal"],
                line_total=totals["line_total"],
            )
        )
    totals = _compute_po_totals(po.line_items)
    po.subtotal = totals["subtotal"]
    po.total_tax = totals["total_tax"]
    po.grand_total = totals["grand_total"]
    _rollup_fulfillment(po)


def _line_response(item: PurchaseOrderLineItem) -> dict:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "sort_order": item.sort_order,
        "description": item.description,
        "sku": item.sku,
        "unit": item.unit,
        "ordered_quantity": _float(item.ordered_quantity),
        "received_quantity": _float(item.received_quantity),
        "billed_quantity": _float(item.billed_quantity),
        "pending_receipt_quantity": _line_pending_receipt(item),
        "pending_billing_quantity": _line_pending_billing(item),
        "unit_price": _float(item.unit_price),
        "tax_rate": _float(item.tax_rate),
        "line_subtotal": _float(item.line_subtotal),
        "line_total": _float(item.line_total),
        "billed_amount": _float(item.billed_amount),
        "product_name": item.product.name if item.product else None,
    }


def _po_response(po: PurchaseOrder) -> PurchaseOrderResponse:
    pending_receipt_value = sum(_float(_line_pending_receipt_value(li)) for li in po.line_items)
    pending_billing_value = sum(_float(_line_pending_billing_value(li)) for li in po.line_items)
    grand = _float(po.grand_total)
    received = _float(po.received_value)
    billed = _float(po.billed_value)
    return PurchaseOrderResponse(
        id=po.id,
        po_number=po.po_number,
        title=po.title,
        vendor_name=po.vendor_name,
        vendor_contact=po.vendor_contact,
        vendor_email=po.vendor_email,
        vendor_phone=po.vendor_phone,
        status=po.status,
        currency=po.currency,
        payment_terms=po.payment_terms,
        po_date=po.po_date,
        expected_delivery_date=po.expected_delivery_date,
        delivery_location=po.delivery_location,
        notes=po.notes,
        internal_reference=po.internal_reference,
        vendor_quote_reference=po.vendor_quote_reference,
        cost_center=po.cost_center,
        rejection_reason=po.rejection_reason,
        reviewer_comments=po.reviewer_comments,
        subtotal=_float(po.subtotal),
        total_tax=_float(po.total_tax),
        grand_total=grand,
        received_value=received,
        billed_value=billed,
        pending_receipt_value=pending_receipt_value,
        pending_billing_value=pending_billing_value,
        received_percent=round((received / grand) * 100, 1) if grand > 0 else 0.0,
        billed_percent=round((billed / grand) * 100, 1) if grand > 0 else 0.0,
        deal_id=po.deal_id,
        deal_title=po.deal.title if po.deal else None,
        contact_id=po.contact_id,
        contact_name=po.contact.name if po.contact else None,
        created_by_id=po.created_by_id,
        created_by_name=po.created_by.name if po.created_by else None,
        reviewed_by_name=po.reviewed_by.name if po.reviewed_by else None,
        approved_by_name=po.approved_by.name if po.approved_by else None,
        sent_by_name=po.sent_by.name if po.sent_by else None,
        closed_by_name=po.closed_by.name if po.closed_by else None,
        submitted_at=po.submitted_at,
        reviewed_at=po.reviewed_at,
        approved_at=po.approved_at,
        sent_at=po.sent_at,
        closed_at=po.closed_at,
        cancelled_at=po.cancelled_at,
        created_at=po.created_at,
        updated_at=po.updated_at,
        line_items=[_line_response(li) for li in po.line_items],
        receipts=[
            PurchaseOrderReceiptResponse(
                id=r.id,
                line_item_id=r.line_item_id,
                line_description=r.line_item.description if r.line_item else None,
                quantity=_float(r.quantity),
                receipt_date=r.receipt_date,
                grn_reference=r.grn_reference,
                notes=r.notes,
                recorded_by_name=r.recorded_by.name if r.recorded_by else None,
                created_at=r.created_at,
            )
            for r in po.receipts
        ],
        billings=[
            PurchaseOrderBillingResponse(
                id=b.id,
                line_item_id=b.line_item_id,
                line_description=b.line_item.description if b.line_item else None,
                quantity=_float(b.quantity),
                amount=_float(b.amount),
                bill_reference=b.bill_reference,
                notes=b.notes,
                recorded_by_name=b.recorded_by.name if b.recorded_by else None,
                created_at=b.created_at,
            )
            for b in po.billings
        ],
        attachments=[
            PurchaseOrderAttachmentResponse(
                id=a.id,
                original_filename=a.original_filename,
                content_type=a.content_type,
                file_size=a.file_size,
                uploaded_by_name=a.uploaded_by.name if a.uploaded_by else None,
                created_at=a.created_at,
            )
            for a in po.attachments
        ],
    )


def _get_po(db: Session, po_id: int, company_id: int) -> PurchaseOrder:
    po = (
        db.query(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.created_by),
            joinedload(PurchaseOrder.reviewed_by),
            joinedload(PurchaseOrder.approved_by),
            joinedload(PurchaseOrder.sent_by),
            joinedload(PurchaseOrder.closed_by),
            joinedload(PurchaseOrder.deal),
            joinedload(PurchaseOrder.contact),
            joinedload(PurchaseOrder.line_items).joinedload(PurchaseOrderLineItem.product),
            joinedload(PurchaseOrder.receipts).joinedload(PurchaseOrderReceipt.line_item),
            joinedload(PurchaseOrder.receipts).joinedload(PurchaseOrderReceipt.recorded_by),
            joinedload(PurchaseOrder.billings).joinedload(PurchaseOrderBilling.line_item),
            joinedload(PurchaseOrder.billings).joinedload(PurchaseOrderBilling.recorded_by),
            joinedload(PurchaseOrder.attachments).joinedload(PurchaseOrderAttachment.uploaded_by),
        )
        .filter(PurchaseOrder.id == po_id, PurchaseOrder.company_id == company_id)
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


def _can_edit(po: PurchaseOrder, user: User, db: Session) -> bool:
    if role_has_permission(db, user.role, "purchase_orders.edit_all"):
        return po.status in EDITABLE_STATUSES
    if role_has_permission(db, user.role, "purchase_orders.edit_own") and po.created_by_id == user.id:
        return po.status in EDITABLE_STATUSES
    return False


def _validate_fk(db: Session, model, fk_id: int | None, company_id: int, label: str) -> None:
    if fk_id is None:
        return
    row = db.query(model).filter(model.id == fk_id, model.company_id == company_id).first()
    if not row:
        raise HTTPException(status_code=400, detail=f"Invalid {label}")


@router.get("/statuses", response_model=list[PurchaseOrderStatusOption])
def statuses(_: User = Depends(require_permission("purchase_orders.view"))):
    return [PurchaseOrderStatusOption(value=s, label=PO_STATUS_LABELS[s]) for s in PO_STATUSES]


@router.get("/payment-terms", response_model=list[PurchaseOrderPaymentTermOption])
def payment_terms(_: User = Depends(require_permission("purchase_orders.view"))):
    return [PurchaseOrderPaymentTermOption(value=t, label=PAYMENT_TERM_LABELS[t]) for t in PAYMENT_TERMS]


@router.get("/stats/summary", response_model=PurchaseOrderStatsResponse)
def stats(user: User = Depends(require_permission("purchase_orders.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    now = datetime.now(timezone.utc)
    open_statuses = [
        "submitted", "under_review", "approved", "sent_to_vendor",
        "partially_received", "fully_received", "partially_billed", "fully_billed",
    ]
    pos = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.line_items)).filter(
        PurchaseOrder.company_id == company.id
    ).all()

    open_value = 0.0
    pending_approval = 0.0
    pending_receipt = 0.0
    pending_billing = 0.0
    overdue = 0
    vendor_open: dict[str, float] = {}

    for po in pos:
        grand = _float(po.grand_total)
        if po.status in open_statuses:
            open_value += grand
            vendor_open[po.vendor_name] = vendor_open.get(po.vendor_name, 0) + grand
        if po.status in {"submitted", "under_review"}:
            pending_approval += grand
        if po.status in RECEIPT_STATUSES:
            pending_receipt += sum(_float(_line_pending_receipt_value(li)) for li in po.line_items)
        if po.status in BILLING_STATUSES:
            pending_billing += sum(_float(_line_pending_billing_value(li)) for li in po.line_items)
        if po.expected_delivery_date and po.expected_delivery_date < now and po.status in {
            "sent_to_vendor", "partially_received", "approved",
        }:
            overdue += 1

    top_vendor = max(vendor_open, key=vendor_open.get) if vendor_open else None
    return PurchaseOrderStatsResponse(
        open_po_value=open_value,
        pending_approval_amount=pending_approval,
        pending_receipt_value=pending_receipt,
        pending_billing_value=pending_billing,
        overdue_delivery_count=overdue,
        top_vendor=top_vendor,
        by_vendor=[{"name": k, "value": v} for k, v in sorted(vendor_open.items(), key=lambda x: x[1], reverse=True)[:10]],
    )


@router.get("/approval-queue", response_model=PurchaseOrderListResponse)
def approval_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("purchase_orders.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.created_by),
            joinedload(PurchaseOrder.line_items).joinedload(PurchaseOrderLineItem.product),
            joinedload(PurchaseOrder.deal),
            joinedload(PurchaseOrder.contact),
            joinedload(PurchaseOrder.receipts),
            joinedload(PurchaseOrder.billings),
            joinedload(PurchaseOrder.attachments),
        )
        .filter(PurchaseOrder.company_id == company.id, PurchaseOrder.status.in_(["submitted", "under_review"]))
    )
    total = query.count()
    items = query.order_by(PurchaseOrder.submitted_at.asc().nullslast(), PurchaseOrder.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return PurchaseOrderListResponse(items=[_po_response(po) for po in items], total=total, page=page, limit=limit)


@router.get("", response_model=PurchaseOrderListResponse)
def list_purchase_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    fulfillment: str | None = None,
    mine: bool = False,
    search: str | None = None,
    user: User = Depends(require_permission("purchase_orders.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.created_by),
            joinedload(PurchaseOrder.line_items).joinedload(PurchaseOrderLineItem.product),
            joinedload(PurchaseOrder.deal),
            joinedload(PurchaseOrder.contact),
            joinedload(PurchaseOrder.receipts),
            joinedload(PurchaseOrder.billings),
            joinedload(PurchaseOrder.attachments),
        )
        .filter(PurchaseOrder.company_id == company.id)
    )
    if mine:
        query = query.filter(PurchaseOrder.created_by_id == user.id)
    if status:
        _validate_status(status)
        query = query.filter(PurchaseOrder.status == status)
    if fulfillment == "pending_receipt":
        query = query.filter(PurchaseOrder.status.in_(list(RECEIPT_STATUSES)))
    elif fulfillment == "pending_billing":
        query = query.filter(PurchaseOrder.status.in_(list(BILLING_STATUSES)))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            PurchaseOrder.title.ilike(term),
            PurchaseOrder.vendor_name.ilike(term),
            PurchaseOrder.po_number.ilike(term),
        ))
    total = query.count()
    items = query.order_by(PurchaseOrder.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return PurchaseOrderListResponse(items=[_po_response(po) for po in items], total=total, page=page, limit=limit)


@router.post("", response_model=PurchaseOrderResponse, status_code=201)
def create_purchase_order(
    payload: PurchaseOrderCreateRequest,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    _validate_payment_terms(payload.payment_terms)
    _validate_fk(db, Deal, payload.deal_id, company.id, "deal")
    _validate_fk(db, Contact, payload.contact_id, company.id, "contact")
    for item in payload.line_items:
        if item.product_id:
            product = db.query(Product).filter(Product.id == item.product_id, Product.company_id == company.id).first()
            if not product:
                raise HTTPException(status_code=400, detail="Invalid product on line item")

    po = PurchaseOrder(
        company_id=company.id,
        created_by_id=user.id,
        title=payload.title.strip(),
        vendor_name=payload.vendor_name.strip(),
        vendor_contact=payload.vendor_contact,
        vendor_email=payload.vendor_email,
        vendor_phone=payload.vendor_phone,
        currency=payload.currency,
        payment_terms=payload.payment_terms,
        po_date=payload.po_date,
        expected_delivery_date=payload.expected_delivery_date,
        delivery_location=payload.delivery_location,
        notes=payload.notes,
        internal_reference=payload.internal_reference,
        vendor_quote_reference=payload.vendor_quote_reference,
        cost_center=payload.cost_center,
        deal_id=payload.deal_id,
        contact_id=payload.contact_id,
        status="draft",
    )
    db.add(po)
    db.flush()
    _apply_line_items(po, payload.line_items)
    db.commit()
    db.refresh(po)
    log_activity(db, user.id, user.email, "purchase_order_created", f"PO draft: {po.title}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.get("/{po_id}", response_model=PurchaseOrderResponse)
def get_purchase_order(
    po_id: int,
    user: User = Depends(require_permission("purchase_orders.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    return _po_response(_get_po(db, po_id, company.id))


@router.put("/{po_id}", response_model=PurchaseOrderResponse)
def update_purchase_order(
    po_id: int,
    payload: PurchaseOrderUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.edit_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if not _can_edit(po, user, db):
        raise HTTPException(status_code=403, detail="You cannot edit this purchase order")
    _validate_payment_terms(payload.payment_terms)
    _validate_fk(db, Deal, payload.deal_id, company.id, "deal")
    _validate_fk(db, Contact, payload.contact_id, company.id, "contact")

    po.title = payload.title.strip()
    po.vendor_name = payload.vendor_name.strip()
    po.vendor_contact = payload.vendor_contact
    po.vendor_email = payload.vendor_email
    po.vendor_phone = payload.vendor_phone
    po.currency = payload.currency
    po.payment_terms = payload.payment_terms
    po.po_date = payload.po_date
    po.expected_delivery_date = payload.expected_delivery_date
    po.delivery_location = payload.delivery_location
    po.notes = payload.notes
    po.internal_reference = payload.internal_reference
    po.vendor_quote_reference = payload.vendor_quote_reference
    po.cost_center = payload.cost_center
    po.deal_id = payload.deal_id
    po.contact_id = payload.contact_id
    _apply_line_items(po, payload.line_items)
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_updated", f"PO updated: {po.title}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.delete("/{po_id}", status_code=204)
def delete_purchase_order(
    po_id: int,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.delete")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase orders can be deleted")
    if not _can_edit(po, user, db) and not role_has_permission(db, user.role, "purchase_orders.edit_all"):
        raise HTTPException(status_code=403, detail="You cannot delete this purchase order")
    db.delete(po)
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_deleted", f"PO deleted: {po.title}", get_client_ip(request))


@router.post("/{po_id}/submit", response_model=PurchaseOrderResponse)
def submit_purchase_order(
    po_id: int,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.submit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.created_by_id != user.id and not role_has_permission(db, user.role, "purchase_orders.edit_all"):
        raise HTTPException(status_code=403, detail="You cannot submit this purchase order")
    if po.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected POs can be submitted")
    if not po.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")

    po.po_number = po.po_number or _generate_po_number(db, company)
    po.submitted_at = datetime.now(timezone.utc)
    po.rejection_reason = None
    if _float(po.grand_total) >= APPROVAL_THRESHOLD:
        _set_status(po, "under_review")
    else:
        _set_status(po, "submitted")
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_submitted", f"PO submitted: {po.po_number}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.post("/{po_id}/approve", response_model=PurchaseOrderResponse)
def approve_purchase_order(
    po_id: int,
    payload: PurchaseOrderReviewRequest,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=400, detail="PO is not awaiting approval")
    now = datetime.now(timezone.utc)
    po.reviewed_by_id = user.id
    po.approved_by_id = user.id
    po.reviewed_at = now
    po.approved_at = now
    po.reviewer_comments = payload.comments
    _set_status(po, "approved")
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_approved", f"PO approved: {po.po_number}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.post("/{po_id}/reject", response_model=PurchaseOrderResponse)
def reject_purchase_order(
    po_id: int,
    payload: PurchaseOrderRejectRequest,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.reject")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=400, detail="PO is not awaiting approval")
    now = datetime.now(timezone.utc)
    po.reviewed_by_id = user.id
    po.reviewed_at = now
    po.rejection_reason = payload.reason
    po.reviewer_comments = payload.comments
    _set_status(po, "rejected")
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_rejected", f"PO rejected: {po.po_number}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.post("/{po_id}/send", response_model=PurchaseOrderResponse)
def send_to_vendor(
    po_id: int,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.send")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved POs can be sent to vendor")
    po.sent_by_id = user.id
    po.sent_at = datetime.now(timezone.utc)
    _set_status(po, "sent_to_vendor")
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_sent", f"PO sent: {po.po_number}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.post("/{po_id}/record-receipt", response_model=PurchaseOrderResponse)
def record_receipt(
    po_id: int,
    payload: PurchaseOrderRecordReceiptRequest,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.record_receipt")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status not in RECEIPT_STATUSES:
        raise HTTPException(status_code=400, detail="Receipts can only be recorded after PO is sent to vendor")

    line = next((li for li in po.line_items if li.id == payload.line_item_id), None)
    if not line:
        raise HTTPException(status_code=404, detail="Line item not found")
    new_received = _float(line.received_quantity) + payload.quantity
    if new_received > _float(line.ordered_quantity):
        raise HTTPException(status_code=400, detail="Received quantity cannot exceed ordered quantity")

    line.received_quantity = new_received
    po.receipts.append(
        PurchaseOrderReceipt(
            line_item_id=line.id,
            recorded_by_id=user.id,
            quantity=payload.quantity,
            receipt_date=payload.receipt_date,
            grn_reference=payload.grn_reference,
            notes=payload.notes,
        )
    )
    _rollup_fulfillment(po)
    _sync_fulfillment_status(po)
    db.flush()
    create_incoming_po_inspection(db, company, po, line.product_id)
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_receipt_recorded", f"Receipt on {po.po_number}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.post("/{po_id}/record-billing", response_model=PurchaseOrderResponse)
def record_billing(
    po_id: int,
    payload: PurchaseOrderRecordBillingRequest,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.record_billing")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status not in BILLING_STATUSES:
        raise HTTPException(status_code=400, detail="Billing can only be recorded after receipt progress exists")

    line = next((li for li in po.line_items if li.id == payload.line_item_id), None)
    if not line:
        raise HTTPException(status_code=404, detail="Line item not found")
    new_billed_qty = _float(line.billed_quantity) + payload.quantity
    if new_billed_qty > _float(line.received_quantity):
        raise HTTPException(status_code=400, detail="Billed quantity cannot exceed received quantity")

    line.billed_quantity = new_billed_qty
    line.billed_amount = _float(line.billed_amount) + payload.amount
    po.billings.append(
        PurchaseOrderBilling(
            line_item_id=line.id,
            recorded_by_id=user.id,
            quantity=payload.quantity,
            amount=payload.amount,
            bill_reference=payload.bill_reference,
            notes=payload.notes,
        )
    )
    _rollup_fulfillment(po)
    _sync_fulfillment_status(po)
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_billing_recorded", f"Billing on {po.po_number}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.post("/{po_id}/close", response_model=PurchaseOrderResponse)
def close_purchase_order(
    po_id: int,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.close")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status not in {"fully_billed", "partially_billed", "fully_received"}:
        raise HTTPException(status_code=400, detail="PO cannot be closed in its current status")
    po.closed_by_id = user.id
    po.closed_at = datetime.now(timezone.utc)
    _set_status(po, "closed")
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_closed", f"PO closed: {po.po_number}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.post("/{po_id}/cancel", response_model=PurchaseOrderResponse)
def cancel_purchase_order(
    po_id: int,
    request: Request,
    user: User = Depends(require_permission("purchase_orders.edit_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if po.status in {"closed", "cancelled"}:
        raise HTTPException(status_code=400, detail="PO is already finalised")
    po.cancelled_at = datetime.now(timezone.utc)
    _set_status(po, "cancelled")
    db.commit()
    log_activity(db, user.id, user.email, "purchase_order_cancelled", f"PO cancelled: {po.po_number}", get_client_ip(request))
    return _po_response(_get_po(db, po.id, company.id))


@router.post("/{po_id}/attachments", response_model=PurchaseOrderAttachmentResponse)
async def upload_attachment(
    po_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("purchase_orders.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed. Use JPG, PNG, WEBP, or PDF.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "file").suffix or ".bin"
    stored = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_ROOT / stored
    dest.write_bytes(content)

    attachment = PurchaseOrderAttachment(
        purchase_order_id=po.id,
        uploaded_by_id=user.id,
        original_filename=file.filename or stored,
        stored_filename=stored,
        content_type=file.content_type,
        file_size=len(content),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    log_activity(db, user.id, user.email, "purchase_order_attachment_uploaded", f"Attachment on {po.po_number}", get_client_ip(request))
    return PurchaseOrderAttachmentResponse(
        id=attachment.id,
        original_filename=attachment.original_filename,
        content_type=attachment.content_type,
        file_size=attachment.file_size,
        uploaded_by_name=user.name,
        created_at=attachment.created_at,
    )


@router.get("/{po_id}/attachments/{attachment_id}/download")
def download_attachment(
    po_id: int,
    attachment_id: int,
    user: User = Depends(require_permission("purchase_orders.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    po = _get_po(db, po_id, company.id)
    attachment = next((a for a in po.attachments if a.id == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = UPLOAD_ROOT / attachment.stored_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    return FileResponse(path, filename=attachment.original_filename, media_type=attachment.content_type or "application/octet-stream")
