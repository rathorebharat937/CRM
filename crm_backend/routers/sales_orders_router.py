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
from models import (
    Company,
    Contact,
    Deal,
    Lead,
    Product,
    Quotation,
    SalesOrder,
    SalesOrderLineItem,
    SalesOrderMilestone,
    SystemSetting,
    User,
)
from sales_order_config import (
    ALLOWED_TRANSITIONS,
    CONVERTIBLE_QUOTE_STATUSES,
    DEFAULT_ORDER_PREFIX,
    EDITABLE_STATUSES,
    FINAL_STATUSES,
    ORDER_STATUS_LABELS,
    ORDER_STATUSES,
    ORDER_TYPES,
    SOURCE_TYPES,
)
from schemas import (
    QuotationCompanyBranding,
    SalesOrderClientActionRequest,
    SalesOrderCreateRequest,
    SalesOrderLineItemFields,
    SalesOrderLineItemResponse,
    SalesOrderListResponse,
    SalesOrderMilestoneFields,
    SalesOrderMilestoneResponse,
    SalesOrderProgressRequest,
    SalesOrderPublicResponse,
    SalesOrderReasonRequest,
    SalesOrderResponse,
    SalesOrderSendConfirmationRequest,
    SalesOrderStatsResponse,
    SalesOrderStatusOption,
    SalesOrderUpdateRequest,
    SalesOrderVersionSummary,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/sales-orders", tags=["sales-orders"])
public_router = APIRouter(prefix="/public/orders", tags=["public-orders"])




def _decimal(value: float | Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _float(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _validate_status(status: str) -> None:
    if status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(ORDER_STATUSES)}")


def _set_status(order: SalesOrder, new_status: str) -> None:
    _validate_status(new_status)
    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if new_status not in allowed and order.status != new_status:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {order.status} to {new_status}")
    order.status = new_status
    order.last_status_change_at = datetime.now(timezone.utc)


def _get_order(db: Session, order_id: int, company_id: int) -> SalesOrder:
    order = (
        db.query(SalesOrder)
        .options(
            joinedload(SalesOrder.assigned_to),
            joinedload(SalesOrder.created_by),
            joinedload(SalesOrder.confirmed_by),
            joinedload(SalesOrder.quotation),
            joinedload(SalesOrder.deal),
            joinedload(SalesOrder.lead),
            joinedload(SalesOrder.contact),
            joinedload(SalesOrder.line_items).joinedload(SalesOrderLineItem.product),
            joinedload(SalesOrder.milestones).joinedload(SalesOrderMilestone.owner),
        )
        .filter(SalesOrder.id == order_id, SalesOrder.company_id == company_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return order


def _get_order_by_token(db: Session, token: str) -> SalesOrder:
    order = (
        db.query(SalesOrder)
        .options(
            joinedload(SalesOrder.line_items),
            joinedload(SalesOrder.milestones),
            joinedload(SalesOrder.quotation),
            joinedload(SalesOrder.company),
        )
        .filter(SalesOrder.share_token == token)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return order


def _validate_staff(db: Session, user_id: int | None, company_id: int):
    if user_id is None:
        return
    staff = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == company_id, User.role.in_(STAFF_ROLES), User.status == "active")
        .first()
    )
    if not staff:
        raise HTTPException(status_code=400, detail="Invalid staff member")


def _validate_fk(db: Session, model, fk_id: int | None, company_id: int, label: str):
    if fk_id is None:
        return
    row = db.query(model).filter(model.id == fk_id, model.company_id == company_id).first()
    if not row:
        raise HTTPException(status_code=400, detail=f"Invalid {label}")


def _compute_totals(line_items: list, header_discount_amount: float, header_discount_percent: float) -> dict[str, Decimal]:
    subtotal = Decimal("0")
    line_discount_total = Decimal("0")
    total_tax = Decimal("0")

    for item in line_items:
        qty = _decimal(item.quantity if hasattr(item, "quantity") else item["quantity"])
        unit_price = _decimal(item.unit_price if hasattr(item, "unit_price") else item["unit_price"])
        discount_percent = _decimal(item.discount_percent if hasattr(item, "discount_percent") else item["discount_percent"])
        discount_amount = _decimal(item.discount_amount if hasattr(item, "discount_amount") else item["discount_amount"])
        tax_rate = _decimal(item.tax_rate if hasattr(item, "tax_rate") else item["tax_rate"])

        line_subtotal = qty * unit_price
        line_discount = discount_amount if discount_amount > 0 else line_subtotal * (discount_percent / Decimal("100"))
        after_discount = max(line_subtotal - line_discount, Decimal("0"))
        line_tax = after_discount * (tax_rate / Decimal("100"))

        subtotal += line_subtotal
        line_discount_total += line_discount
        total_tax += line_tax

    after_line_discounts = max(subtotal - line_discount_total, Decimal("0"))
    hdr_amount = _decimal(header_discount_amount)
    hdr_percent = _decimal(header_discount_percent)
    header_discount = hdr_amount if hdr_amount > 0 else after_line_discounts * (hdr_percent / Decimal("100"))
    taxable = max(after_line_discounts - header_discount, Decimal("0"))
    tax_scale = taxable / after_line_discounts if after_line_discounts > 0 else Decimal("0")
    total_tax = total_tax * tax_scale
    grand_total = taxable + total_tax

    return {
        "subtotal": subtotal,
        "line_discount_total": line_discount_total,
        "header_discount_amount": header_discount,
        "header_discount_percent": hdr_percent,
        "total_tax": total_tax,
        "grand_total": grand_total,
    }


def _generate_order_number(db: Session, company_id: int) -> str:
    count = db.query(func.count(SalesOrder.id)).filter(SalesOrder.company_id == company_id).scalar()
    return f"{DEFAULT_ORDER_PREFIX}{count + 1:05d}"


def _line_response(item: SalesOrderLineItem) -> SalesOrderLineItemResponse:
    return SalesOrderLineItemResponse(
        id=item.id,
        product_id=item.product_id,
        product_name=item.product.name if item.product else None,
        quotation_line_item_id=item.quotation_line_item_id,
        sort_order=item.sort_order,
        section=item.section,
        item_name=item.item_name,
        description=item.description,
        quantity=_float(item.quantity),
        unit=item.unit,
        unit_price=_float(item.unit_price),
        discount_percent=_float(item.discount_percent),
        discount_amount=_float(item.discount_amount),
        tax_rate=_float(item.tax_rate),
        line_subtotal=_float(item.line_subtotal),
        line_total=_float(item.line_total),
        fulfilled_quantity=_float(item.fulfilled_quantity),
        fulfillment_status=item.fulfillment_status,
    )


def _milestone_response(ms: SalesOrderMilestone) -> SalesOrderMilestoneResponse:
    return SalesOrderMilestoneResponse(
        id=ms.id,
        sort_order=ms.sort_order,
        title=ms.title,
        description=ms.description,
        status=ms.status,
        due_date=ms.due_date,
        owner_id=ms.owner_id,
        owner_name=ms.owner.name if ms.owner else None,
        completed_at=ms.completed_at,
    )


def _order_response(order: SalesOrder) -> SalesOrderResponse:
    share_url = f"{FRONTEND_URL}/order/{order.share_token}" if order.share_token else None
    return SalesOrderResponse(
        id=order.id,
        company_id=order.company_id,
        order_number=order.order_number,
        title=order.title,
        status=order.status,
        version=order.version,
        order_type=order.order_type,
        source_type=order.source_type,
        currency=order.currency,
        order_date=order.order_date,
        confirmation_date=order.confirmation_date,
        due_date=order.due_date,
        internal_target_date=order.internal_target_date,
        quotation_id=order.quotation_id,
        quotation_number=order.quotation.quote_number if order.quotation else None,
        deal_id=order.deal_id,
        deal_title=order.deal.title if order.deal else None,
        lead_id=order.lead_id,
        lead_name=order.lead.name if order.lead else None,
        contact_id=order.contact_id,
        contact_name=order.contact.name if order.contact else None,
        assigned_to_id=order.assigned_to_id,
        assigned_to_name=order.assigned_to.name if order.assigned_to else None,
        created_by_id=order.created_by_id,
        created_by_name=order.created_by.name if order.created_by else None,
        confirmed_by_id=order.confirmed_by_id,
        confirmed_by_name=order.confirmed_by.name if order.confirmed_by else None,
        parent_order_id=order.parent_order_id,
        root_order_id=order.root_order_id,
        client_name=order.client_name,
        client_email=order.client_email,
        client_phone=order.client_phone,
        client_org=order.client_org,
        attention_to=order.attention_to,
        billing_address=order.billing_address,
        delivery_address=order.delivery_address,
        subtotal=_float(order.subtotal),
        line_discount_total=_float(order.line_discount_total),
        header_discount_amount=_float(order.header_discount_amount),
        header_discount_percent=_float(order.header_discount_percent),
        total_tax=_float(order.total_tax),
        grand_total=_float(order.grand_total),
        billing_notes=order.billing_notes,
        payment_milestone_notes=order.payment_milestone_notes,
        delivery_instructions=order.delivery_instructions,
        internal_notes=order.internal_notes,
        hold_reason=order.hold_reason,
        cancellation_reason=order.cancellation_reason,
        completion_notes=order.completion_notes,
        fulfillment_progress=order.fulfillment_progress,
        billing_status=order.billing_status,
        preparation_status=order.preparation_status,
        share_token=order.share_token,
        share_url=share_url,
        sent_for_confirmation_at=order.sent_for_confirmation_at,
        confirmed_at=order.confirmed_at,
        closed_at=order.closed_at,
        cancelled_at=order.cancelled_at,
        hold_at=order.hold_at,
        hold_resume_date=order.hold_resume_date,
        last_status_change_at=order.last_status_change_at,
        line_items=[_line_response(li) for li in order.line_items],
        milestones=[_milestone_response(ms) for ms in order.milestones],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _company_branding(company: Company, settings: SystemSetting | None) -> QuotationCompanyBranding:
    return QuotationCompanyBranding(
        display_name=company.display_name,
        legal_name=company.legal_name,
        email=company.email,
        phone=company.phone,
        website=company.website,
        address_line1=company.address_line1,
        address_line2=company.address_line2,
        city=company.city,
        state=company.state,
        pincode=company.pincode,
        country=company.country,
        gstin=company.gstin,
        pan=company.pan,
        logo_filename=settings.logo_filename if settings else None,
    )


def _apply_line_items(order: SalesOrder, line_items: list, db: Session) -> None:
    order.line_items.clear()
    for idx, item in enumerate(line_items):
        _validate_fk(db, Product, item.product_id, order.company_id, "product")
        qty = _decimal(item.quantity)
        unit_price = _decimal(item.unit_price)
        discount_percent = _decimal(item.discount_percent)
        discount_amount = _decimal(item.discount_amount)
        tax_rate = _decimal(item.tax_rate)
        line_subtotal = qty * unit_price
        line_discount = discount_amount if discount_amount > 0 else line_subtotal * (discount_percent / Decimal("100"))
        after_discount = max(line_subtotal - line_discount, Decimal("0"))
        line_tax = after_discount * (tax_rate / Decimal("100"))
        line_total = after_discount + line_tax

        order.line_items.append(
            SalesOrderLineItem(
                product_id=item.product_id,
                quotation_line_item_id=item.quotation_line_item_id,
                sort_order=item.sort_order if item.sort_order else idx,
                section=item.section,
                item_name=item.item_name.strip(),
                description=item.description,
                quantity=qty,
                unit=item.unit or "Service",
                unit_price=unit_price,
                discount_percent=discount_percent,
                discount_amount=discount_amount,
                tax_rate=tax_rate,
                line_subtotal=line_subtotal,
                line_total=line_total,
            )
        )


def _apply_milestones(order: SalesOrder, milestones: list, db: Session) -> None:
    order.milestones.clear()
    for idx, ms in enumerate(milestones):
        _validate_staff(db, ms.owner_id, order.company_id)
        order.milestones.append(
            SalesOrderMilestone(
                sort_order=ms.sort_order if ms.sort_order else idx,
                title=ms.title.strip(),
                description=ms.description,
                status=ms.status or "pending",
                due_date=ms.due_date,
                owner_id=ms.owner_id,
            )
        )


def _validate_dates(order_date: datetime | None, due_date: datetime | None) -> None:
    if order_date and due_date and due_date < order_date:
        raise HTTPException(status_code=400, detail="Due date cannot be earlier than order date")


def _build_order(
    db: Session,
    company: Company,
    payload: SalesOrderCreateRequest,
    user: User,
    *,
    source_type: str = "manual",
    order_number: str | None = None,
    version: int = 1,
    parent_order_id: int | None = None,
    root_order_id: int | None = None,
    quotation_id: int | None = None,
) -> SalesOrder:
    _validate_staff(db, payload.assigned_to_id, company.id)
    _validate_fk(db, Deal, payload.deal_id, company.id, "deal")
    _validate_fk(db, Lead, payload.lead_id, company.id, "lead")
    _validate_fk(db, Contact, payload.contact_id, company.id, "contact")
    if payload.order_type not in ORDER_TYPES:
        raise HTTPException(status_code=400, detail=f"Order type must be one of: {', '.join(ORDER_TYPES)}")
    if source_type not in SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid source type")

    order_date = payload.order_date or datetime.now(timezone.utc)
    _validate_dates(order_date, payload.due_date)

    totals = _compute_totals(payload.line_items, payload.header_discount_amount, payload.header_discount_percent)

    order = SalesOrder(
        company_id=company.id,
        created_by_id=user.id,
        quotation_id=quotation_id or payload.quotation_id,
        order_number=order_number or _generate_order_number(db, company.id),
        title=payload.title.strip(),
        status="draft",
        version=version,
        order_type=payload.order_type,
        source_type=source_type,
        currency=payload.currency or company.currency or "INR",
        order_date=order_date,
        due_date=payload.due_date,
        internal_target_date=payload.internal_target_date,
        deal_id=payload.deal_id,
        lead_id=payload.lead_id,
        contact_id=payload.contact_id,
        assigned_to_id=payload.assigned_to_id or user.id,
        client_name=payload.client_name,
        client_email=payload.client_email,
        client_phone=payload.client_phone,
        client_org=payload.client_org,
        attention_to=payload.attention_to,
        billing_address=payload.billing_address,
        delivery_address=payload.delivery_address,
        subtotal=totals["subtotal"],
        line_discount_total=totals["line_discount_total"],
        header_discount_amount=totals["header_discount_amount"],
        header_discount_percent=totals["header_discount_percent"],
        total_tax=totals["total_tax"],
        grand_total=totals["grand_total"],
        billing_notes=payload.billing_notes,
        payment_milestone_notes=payload.payment_milestone_notes,
        delivery_instructions=payload.delivery_instructions,
        internal_notes=payload.internal_notes,
        parent_order_id=parent_order_id,
        root_order_id=root_order_id,
    )
    db.add(order)
    db.flush()
    _apply_line_items(order, payload.line_items, db)
    _apply_milestones(order, payload.milestones, db)
    return order


def _update_order_fields(order: SalesOrder, payload: SalesOrderUpdateRequest, db: Session) -> None:
    if order.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Only draft or awaiting confirmation orders can be edited")

    _validate_staff(db, payload.assigned_to_id, order.company_id)
    _validate_fk(db, Deal, payload.deal_id, order.company_id, "deal")
    _validate_fk(db, Lead, payload.lead_id, order.company_id, "lead")
    _validate_fk(db, Contact, payload.contact_id, order.company_id, "contact")
    _validate_dates(payload.order_date, payload.due_date)

    totals = _compute_totals(payload.line_items, payload.header_discount_amount, payload.header_discount_percent)

    order.title = payload.title.strip()
    order.order_type = payload.order_type
    order.currency = payload.currency or order.currency
    order.order_date = payload.order_date
    order.due_date = payload.due_date
    order.internal_target_date = payload.internal_target_date
    order.deal_id = payload.deal_id
    order.lead_id = payload.lead_id
    order.contact_id = payload.contact_id
    order.assigned_to_id = payload.assigned_to_id
    order.client_name = payload.client_name
    order.client_email = payload.client_email
    order.client_phone = payload.client_phone
    order.client_org = payload.client_org
    order.attention_to = payload.attention_to
    order.billing_address = payload.billing_address
    order.delivery_address = payload.delivery_address
    order.subtotal = totals["subtotal"]
    order.line_discount_total = totals["line_discount_total"]
    order.header_discount_amount = totals["header_discount_amount"]
    order.header_discount_percent = totals["header_discount_percent"]
    order.total_tax = totals["total_tax"]
    order.grand_total = totals["grand_total"]
    order.billing_notes = payload.billing_notes
    order.payment_milestone_notes = payload.payment_milestone_notes
    order.delivery_instructions = payload.delivery_instructions
    order.internal_notes = payload.internal_notes

    _apply_line_items(order, payload.line_items, db)
    _apply_milestones(order, payload.milestones, db)


def _order_from_quotation(quote: Quotation) -> SalesOrderCreateRequest:
    return SalesOrderCreateRequest(
        title=f"Order — {quote.title}",
        order_type="mixed",
        currency=quote.currency,
        order_date=datetime.now(timezone.utc),
        due_date=quote.valid_until,
        quotation_id=quote.id,
        deal_id=quote.deal_id,
        lead_id=quote.lead_id,
        contact_id=quote.contact_id,
        assigned_to_id=quote.assigned_to_id,
        client_name=quote.client_name,
        client_email=quote.client_email,
        client_org=quote.client_org,
        attention_to=quote.attention_to,
        billing_address=quote.billing_address,
        delivery_address=quote.shipping_address,
        header_discount_amount=_float(quote.header_discount_amount),
        header_discount_percent=_float(quote.header_discount_percent),
        billing_notes=quote.payment_terms,
        payment_milestone_notes=quote.payment_terms,
        delivery_instructions=quote.deliverables,
        internal_notes=f"Converted from quotation {quote.quote_number}",
        line_items=[
            SalesOrderLineItemFields(
                product_id=li.product_id,
                quotation_line_item_id=li.id,
                sort_order=li.sort_order,
                section=li.section,
                item_name=li.item_name,
                description=li.description,
                quantity=_float(li.quantity),
                unit=li.unit,
                unit_price=_float(li.unit_price),
                discount_percent=_float(li.discount_percent),
                discount_amount=_float(li.discount_amount),
                tax_rate=_float(li.tax_rate),
            )
            for li in quote.line_items
        ],
        milestones=[],
    )


def _recalc_progress(order: SalesOrder) -> None:
    if not order.milestones:
        return
    completed = sum(1 for ms in order.milestones if ms.status == "completed")
    order.fulfillment_progress = int((completed / len(order.milestones)) * 100)


@router.get("/statuses", response_model=list[SalesOrderStatusOption])
def order_statuses(_: User = Depends(require_permission("sales_orders.view"))):
    return [SalesOrderStatusOption(value=s, label=ORDER_STATUS_LABELS[s]) for s in ORDER_STATUSES]


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def order_assignees(user: User = Depends(require_permission("sales_orders.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    staff = (
        db.query(User)
        .filter(User.company_id == company.id, User.role.in_(STAFF_ROLES), User.status == "active")
        .order_by(User.name)
        .all()
    )
    return [StaffAssigneeResponse(id=u.id, name=u.name, email=u.email, role=u.role) for u in staff]


@router.get("/stats/summary", response_model=SalesOrderStatsResponse)
def order_stats(user: User = Depends(require_permission("sales_orders.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    rows = (
        db.query(SalesOrder.status, func.count(SalesOrder.id))
        .filter(SalesOrder.company_id == company.id)
        .group_by(SalesOrder.status)
        .all()
    )
    counts = {s: 0 for s in ORDER_STATUSES}
    for status, count in rows:
        counts[status] = count

    total_value = (
        db.query(func.coalesce(func.sum(SalesOrder.grand_total), 0))
        .filter(SalesOrder.company_id == company.id, SalesOrder.status.notin_(list(FINAL_STATUSES)))
        .scalar()
    )
    confirmed_value = (
        db.query(func.coalesce(func.sum(SalesOrder.grand_total), 0))
        .filter(
            SalesOrder.company_id == company.id,
            SalesOrder.status.in_(["confirmed", "in_preparation", "in_execution", "partially_delivered", "delivered", "in_billing", "completed"]),
        )
        .scalar()
    )

    now = datetime.now(timezone.utc)
    soon = now + timedelta(days=7)
    due_soon = (
        db.query(func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == company.id,
            SalesOrder.due_date.isnot(None),
            SalesOrder.due_date <= soon,
            SalesOrder.due_date >= now,
            SalesOrder.status.notin_(list(FINAL_STATUSES)),
        )
        .scalar()
    )
    overdue = (
        db.query(func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == company.id,
            SalesOrder.due_date.isnot(None),
            SalesOrder.due_date < now,
            SalesOrder.status.notin_(list(FINAL_STATUSES) | {"cancelled"}),
        )
        .scalar()
    )

    return SalesOrderStatsResponse(
        total=sum(counts.values()),
        draft=counts["draft"],
        awaiting_confirmation=counts["awaiting_confirmation"],
        confirmed=counts["confirmed"],
        in_preparation=counts["in_preparation"],
        in_execution=counts["in_execution"],
        partially_delivered=counts["partially_delivered"],
        delivered=counts["delivered"],
        in_billing=counts["in_billing"],
        on_hold=counts["on_hold"],
        completed=counts["completed"],
        cancelled=counts["cancelled"],
        closed=counts["closed"],
        total_value=float(total_value or 0),
        confirmed_value=float(confirmed_value or 0),
        due_soon=due_soon or 0,
        overdue=overdue or 0,
    )


@router.get("", response_model=SalesOrderListResponse)
def list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    owner_id: int | None = None,
    due_in_days: int | None = None,
    sort_by: str = Query("updated_at"),
    sort_dir: str = Query("desc"),
    user: User = Depends(require_permission("sales_orders.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(SalesOrder)
        .options(
            joinedload(SalesOrder.assigned_to),
            joinedload(SalesOrder.quotation),
            joinedload(SalesOrder.deal),
            joinedload(SalesOrder.contact),
            joinedload(SalesOrder.line_items),
            joinedload(SalesOrder.milestones),
        )
        .filter(SalesOrder.company_id == company.id)
    )

    if status:
        _validate_status(status)
        query = query.filter(SalesOrder.status == status)
    if source_type:
        query = query.filter(SalesOrder.source_type == source_type)
    if owner_id:
        query = query.filter(SalesOrder.assigned_to_id == owner_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SalesOrder.order_number.ilike(term),
                SalesOrder.title.ilike(term),
                SalesOrder.client_name.ilike(term),
                SalesOrder.client_org.ilike(term),
            )
        )
    if due_in_days is not None:
        cutoff = datetime.now(timezone.utc) + timedelta(days=due_in_days)
        query = query.filter(
            SalesOrder.due_date.isnot(None),
            SalesOrder.due_date <= cutoff,
            SalesOrder.status.notin_(list(FINAL_STATUSES)),
        )

    sort_column = {
        "updated_at": SalesOrder.updated_at,
        "order_date": SalesOrder.order_date,
        "due_date": SalesOrder.due_date,
        "grand_total": SalesOrder.grand_total,
        "fulfillment_progress": SalesOrder.fulfillment_progress,
    }.get(sort_by, SalesOrder.updated_at)
    query = query.order_by(sort_column.asc() if sort_dir == "asc" else sort_column.desc())

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return SalesOrderListResponse(
        items=[_order_response(o) for o in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=SalesOrderResponse, status_code=201)
def create_order(
    payload: SalesOrderCreateRequest,
    request: Request,
    user: User = Depends(require_permission("sales_orders.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    if not payload.client_name and not payload.contact_id:
        raise HTTPException(status_code=400, detail="Customer is required")
    order = _build_order(db, company, payload, user, source_type="manual")
    db.commit()
    order = _get_order(db, order.id, company.id)
    log_activity(db, "sales_order_created", user_id=user.id, email=user.email, details=f"Order {order.order_number} created", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/from-quotation/{quote_id}", response_model=SalesOrderResponse, status_code=201)
def convert_from_quotation(
    quote_id: int,
    request: Request,
    user: User = Depends(require_permission("sales_orders.convert_from_quote")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = (
        db.query(Quotation)
        .options(joinedload(Quotation.line_items))
        .filter(Quotation.id == quote_id, Quotation.company_id == company.id)
        .first()
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quote.status not in CONVERTIBLE_QUOTE_STATUSES:
        raise HTTPException(status_code=400, detail="Only accepted or approved quotations can be converted")
    if not quote.line_items:
        raise HTTPException(status_code=400, detail="Quotation has no line items")

    existing = db.query(SalesOrder).filter(SalesOrder.quotation_id == quote.id, SalesOrder.status != "cancelled").first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Quotation already converted to order {existing.order_number}")

    payload = _order_from_quotation(quote)
    order = _build_order(db, company, payload, user, source_type="quotation", quotation_id=quote.id)
    db.commit()
    order = _get_order(db, order.id, company.id)
    log_activity(
        db,
        "sales_order_converted_from_quote",
        user_id=user.id,
        email=user.email,
        details=f"Order {order.order_number} created from {quote.quote_number}",
        ip_address=get_client_ip(request),
    )
    return _order_response(order)


@router.get("/{order_id}", response_model=SalesOrderResponse)
def get_order(order_id: int, user: User = Depends(require_permission("sales_orders.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    return _order_response(_get_order(db, order_id, company.id))


@router.put("/{order_id}", response_model=SalesOrderResponse)
def update_order(
    order_id: int,
    payload: SalesOrderUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("sales_orders.edit_draft")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    _update_order_fields(order, payload, db)
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_updated", user_id=user.id, email=user.email, details=f"Order {order.order_number} updated", ip_address=get_client_ip(request))
    return _order_response(order)


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, user: User = Depends(require_permission("sales_orders.edit_draft")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    if order.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft orders can be deleted")
    db.delete(order)
    db.commit()


@router.post("/{order_id}/send-confirmation", response_model=SalesOrderResponse)
def send_confirmation(
    order_id: int,
    payload: SalesOrderSendConfirmationRequest,
    request: Request,
    user: User = Depends(require_permission("sales_orders.confirm")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    if order.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft orders can be sent for confirmation")
    if not order.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    if not order.client_name:
        raise HTTPException(status_code=400, detail="Customer name is required")

    recipient = payload.recipient_email or order.client_email
    if not recipient:
        raise HTTPException(status_code=400, detail="Client email is required")

    if not order.share_token:
        order.share_token = secrets.token_urlsafe(32)
    order.client_email = recipient
    _set_status(order, "awaiting_confirmation")
    order.sent_for_confirmation_at = datetime.now(timezone.utc)
    db.commit()
    order = _get_order(db, order_id, company.id)

    share_url = f"{FRONTEND_URL}/order/{order.share_token}"
    try:
        from services.email_service import render_template, send_email

        html = render_template(
            "order_confirmation.html",
            company_name=company.display_name,
            order_number=order.order_number,
            order_title=order.title,
            client_name=order.client_name or "Client",
            grand_total=f"{order.currency} {_float(order.grand_total):,.2f}",
            due_date=order.due_date.strftime("%d %b %Y") if order.due_date else "TBD",
            share_url=share_url,
            message=payload.message or "",
        )
        send_email(recipient, f"Order confirmation {order.order_number} from {company.display_name}", html)
    except Exception:
        pass

    log_activity(db, "sales_order_sent_for_confirmation", user_id=user.id, email=user.email, details=f"Order {order.order_number} sent to {recipient}", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/confirm-internal", response_model=SalesOrderResponse)
def confirm_internal(
    order_id: int,
    request: Request,
    user: User = Depends(require_permission("sales_orders.confirm")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    if order.status not in {"draft", "awaiting_confirmation"}:
        raise HTTPException(status_code=400, detail="Order cannot be confirmed from current status")
    if not order.client_name:
        raise HTTPException(status_code=400, detail="Customer is required")
    if not order.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")

    _set_status(order, "confirmed")
    order.confirmed_at = datetime.now(timezone.utc)
    order.confirmation_date = datetime.now(timezone.utc)
    order.confirmed_by_id = user.id
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_confirmed", user_id=user.id, email=user.email, details=f"Order {order.order_number} confirmed", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/begin-preparation", response_model=SalesOrderResponse)
def begin_preparation(order_id: int, request: Request, user: User = Depends(require_permission("sales_orders.update_progress")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    _set_status(order, "in_preparation")
    order.preparation_status = "in_progress"
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_progress_updated", user_id=user.id, email=user.email, details=f"Order {order.order_number} in preparation", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/start-execution", response_model=SalesOrderResponse)
def start_execution(order_id: int, request: Request, user: User = Depends(require_permission("sales_orders.update_progress")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    _set_status(order, "in_execution")
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_progress_updated", user_id=user.id, email=user.email, details=f"Order {order.order_number} in execution", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/update-progress", response_model=SalesOrderResponse)
def update_progress(
    order_id: int,
    payload: SalesOrderProgressRequest,
    request: Request,
    user: User = Depends(require_permission("sales_orders.update_progress")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    if order.status in FINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot update progress on a final order")
    order.fulfillment_progress = payload.fulfillment_progress
    if payload.notes:
        note = f"Progress update ({payload.fulfillment_progress}%): {payload.notes}"
        order.internal_notes = f"{order.internal_notes}\n\n{note}" if order.internal_notes else note
    if payload.fulfillment_progress >= 100 and order.status in {"in_preparation", "in_execution", "partially_delivered"}:
        _set_status(order, "delivered")
    elif payload.fulfillment_progress > 0 and order.status in {"in_preparation", "in_execution"}:
        _set_status(order, "partially_delivered")
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_progress_updated", user_id=user.id, email=user.email, details=f"Order {order.order_number} progress {payload.fulfillment_progress}%", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/partial-delivery", response_model=SalesOrderResponse)
def partial_delivery(order_id: int, request: Request, user: User = Depends(require_permission("sales_orders.update_progress")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    _set_status(order, "partially_delivered")
    if order.fulfillment_progress < 50:
        order.fulfillment_progress = 50
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_partially_delivered", user_id=user.id, email=user.email, details=f"Order {order.order_number} partially delivered", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/mark-delivered", response_model=SalesOrderResponse)
def mark_delivered(order_id: int, request: Request, user: User = Depends(require_permission("sales_orders.update_progress")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    _set_status(order, "delivered")
    order.fulfillment_progress = 100
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_progress_updated", user_id=user.id, email=user.email, details=f"Order {order.order_number} delivered", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/billing-handoff", response_model=SalesOrderResponse)
def billing_handoff(order_id: int, request: Request, user: User = Depends(require_permission("sales_orders.update_progress")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    if order.status not in {"confirmed", "delivered", "partially_delivered", "in_execution"}:
        raise HTTPException(status_code=400, detail="Order is not ready for billing handoff")
    _set_status(order, "in_billing")
    order.billing_status = "ready"
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_progress_updated", user_id=user.id, email=user.email, details=f"Order {order.order_number} ready for billing", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/complete", response_model=SalesOrderResponse)
def complete_order(
    order_id: int,
    request: Request,
    payload: SalesOrderProgressRequest | None = None,
    user: User = Depends(require_permission("sales_orders.update_progress")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    _set_status(order, "completed")
    order.fulfillment_progress = 100
    if payload and payload.notes:
        order.completion_notes = payload.notes
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_completed", user_id=user.id, email=user.email, details=f"Order {order.order_number} completed", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/hold", response_model=SalesOrderResponse)
def hold_order(
    order_id: int,
    payload: SalesOrderReasonRequest,
    request: Request,
    user: User = Depends(require_permission("sales_orders.hold")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    if order.status in FINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot place a final order on hold")
    _set_status(order, "on_hold")
    order.hold_reason = payload.reason
    order.hold_at = datetime.now(timezone.utc)
    order.hold_resume_date = payload.resume_date
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_put_on_hold", user_id=user.id, email=user.email, details=f"Order {order.order_number} on hold: {payload.reason}", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/cancel", response_model=SalesOrderResponse)
def cancel_order(
    order_id: int,
    payload: SalesOrderReasonRequest,
    request: Request,
    user: User = Depends(require_permission("sales_orders.cancel")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    if order.status in FINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Order is already in a final state")
    order.status = "cancelled"
    order.cancellation_reason = payload.reason
    order.cancelled_at = datetime.now(timezone.utc)
    order.last_status_change_at = datetime.now(timezone.utc)
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_cancelled", user_id=user.id, email=user.email, details=f"Order {order.order_number} cancelled: {payload.reason}", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/close", response_model=SalesOrderResponse)
def close_order(order_id: int, request: Request, user: User = Depends(require_permission("sales_orders.cancel")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    if order.status not in {"completed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Only completed or cancelled orders can be closed")
    _set_status(order, "closed")
    order.closed_at = datetime.now(timezone.utc)
    order.closed_by_id = user.id
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_closed", user_id=user.id, email=user.email, details=f"Order {order.order_number} closed", ip_address=get_client_ip(request))
    return _order_response(order)


@router.post("/{order_id}/amendment", response_model=SalesOrderResponse, status_code=201)
def create_amendment(order_id: int, request: Request, user: User = Depends(require_permission("sales_orders.amend")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    original = _get_order(db, order_id, company.id)
    if original.status in {"draft", "awaiting_confirmation", "cancelled", "closed"}:
        raise HTTPException(status_code=400, detail="Cannot amend orders in this status")

    root_id = original.root_order_id or original.id
    max_version = (
        db.query(func.max(SalesOrder.version))
        .filter(SalesOrder.company_id == company.id, or_(SalesOrder.root_order_id == root_id, SalesOrder.id == root_id))
        .scalar()
    ) or original.version

    payload = SalesOrderUpdateRequest(
        title=original.title,
        order_type=original.order_type,
        currency=original.currency,
        order_date=datetime.now(timezone.utc),
        due_date=original.due_date,
        internal_target_date=original.internal_target_date,
        quotation_id=original.quotation_id,
        deal_id=original.deal_id,
        lead_id=original.lead_id,
        contact_id=original.contact_id,
        assigned_to_id=original.assigned_to_id,
        client_name=original.client_name,
        client_email=original.client_email,
        client_phone=original.client_phone,
        client_org=original.client_org,
        attention_to=original.attention_to,
        billing_address=original.billing_address,
        delivery_address=original.delivery_address,
        header_discount_amount=_float(original.header_discount_amount),
        header_discount_percent=_float(original.header_discount_percent),
        billing_notes=original.billing_notes,
        payment_milestone_notes=original.payment_milestone_notes,
        delivery_instructions=original.delivery_instructions,
        internal_notes=f"Amendment of {original.order_number}",
        line_items=[
            SalesOrderLineItemFields(
                product_id=li.product_id,
                quotation_line_item_id=li.quotation_line_item_id,
                sort_order=li.sort_order,
                section=li.section,
                item_name=li.item_name,
                description=li.description,
                quantity=_float(li.quantity),
                unit=li.unit,
                unit_price=_float(li.unit_price),
                discount_percent=_float(li.discount_percent),
                discount_amount=_float(li.discount_amount),
                tax_rate=_float(li.tax_rate),
            )
            for li in original.line_items
        ],
        milestones=[
            SalesOrderMilestoneFields(
                sort_order=ms.sort_order,
                title=ms.title,
                description=ms.description,
                status=ms.status,
                due_date=ms.due_date,
                owner_id=ms.owner_id,
            )
            for ms in original.milestones
        ],
    )

    amendment = _build_order(
        db,
        company,
        payload,
        user,
        source_type=original.source_type,
        order_number=f"{original.order_number}-A{max_version + 1}",
        version=max_version + 1,
        parent_order_id=original.id,
        root_order_id=root_id,
        quotation_id=original.quotation_id,
    )
    db.commit()
    amendment = _get_order(db, amendment.id, company.id)
    log_activity(db, "sales_order_amended", user_id=user.id, email=user.email, details=f"Amendment {amendment.order_number} from {original.order_number}", ip_address=get_client_ip(request))
    return _order_response(amendment)


@router.post("/{order_id}/milestones/{milestone_id}/complete", response_model=SalesOrderResponse)
def complete_milestone(
    order_id: int,
    milestone_id: int,
    request: Request,
    user: User = Depends(require_permission("sales_orders.update_progress")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    milestone = next((ms for ms in order.milestones if ms.id == milestone_id), None)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    milestone.status = "completed"
    milestone.completed_at = datetime.now(timezone.utc)
    _recalc_progress(order)
    if order.fulfillment_progress == 100:
        _set_status(order, "delivered")
    elif order.fulfillment_progress > 0 and order.status in {"in_preparation", "in_execution"}:
        _set_status(order, "partially_delivered")
    db.commit()
    order = _get_order(db, order_id, company.id)
    log_activity(db, "sales_order_progress_updated", user_id=user.id, email=user.email, details=f"Milestone completed on {order.order_number}", ip_address=get_client_ip(request))
    return _order_response(order)


@router.get("/{order_id}/versions", response_model=list[SalesOrderVersionSummary])
def list_versions(order_id: int, user: User = Depends(require_permission("sales_orders.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    order = _get_order(db, order_id, company.id)
    root_id = order.root_order_id or order.id
    versions = (
        db.query(SalesOrder)
        .filter(SalesOrder.company_id == company.id, or_(SalesOrder.id == root_id, SalesOrder.root_order_id == root_id))
        .order_by(SalesOrder.version.asc())
        .all()
    )
    return [
        SalesOrderVersionSummary(
            id=v.id,
            order_number=v.order_number,
            version=v.version,
            status=v.status,
            grand_total=_float(v.grand_total),
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in versions
    ]


# --- Public customer endpoints ---


@public_router.get("/{token}", response_model=SalesOrderPublicResponse)
def public_view_order(token: str, db: Session = Depends(get_db)):
    order = _get_order_by_token(db, token)
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == order.company_id).first()
    can_confirm = order.status == "awaiting_confirmation"
    return SalesOrderPublicResponse(
        order=_order_response(order),
        company=_company_branding(order.company, settings),
        can_confirm=can_confirm,
    )


@public_router.post("/{token}/confirm", response_model=SalesOrderPublicResponse)
def public_confirm_order(token: str, db: Session = Depends(get_db)):
    order = _get_order_by_token(db, token)
    if order.status != "awaiting_confirmation":
        raise HTTPException(status_code=400, detail="This order cannot be confirmed")
    order.status = "confirmed"
    order.confirmed_at = datetime.now(timezone.utc)
    order.confirmation_date = datetime.now(timezone.utc)
    order.last_status_change_at = datetime.now(timezone.utc)
    db.commit()
    order = _get_order_by_token(db, token)
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == order.company_id).first()
    return SalesOrderPublicResponse(order=_order_response(order), company=_company_branding(order.company, settings), can_confirm=False)


@public_router.post("/{token}/reject", response_model=SalesOrderPublicResponse)
def public_reject_order(token: str, payload: SalesOrderClientActionRequest, db: Session = Depends(get_db)):
    order = _get_order_by_token(db, token)
    if order.status != "awaiting_confirmation":
        raise HTTPException(status_code=400, detail="This order cannot be rejected")
    order.status = "cancelled"
    order.cancellation_reason = payload.reason or "Rejected by customer"
    order.cancelled_at = datetime.now(timezone.utc)
    order.last_status_change_at = datetime.now(timezone.utc)
    db.commit()
    order = _get_order_by_token(db, token)
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == order.company_id).first()
    return SalesOrderPublicResponse(order=_order_response(order), company=_company_branding(order.company, settings), can_confirm=False)


@public_router.post("/{token}/request-changes", response_model=SalesOrderPublicResponse)
def public_request_changes(token: str, payload: SalesOrderClientActionRequest, db: Session = Depends(get_db)):
    order = _get_order_by_token(db, token)
    if order.status != "awaiting_confirmation":
        raise HTTPException(status_code=400, detail="Cannot request changes on this order")
    note = f"Customer requested changes: {payload.message or payload.reason or 'No details provided'}"
    order.internal_notes = f"{order.internal_notes}\n\n{note}" if order.internal_notes else note
    _set_status(order, "draft")
    db.commit()
    order = _get_order_by_token(db, token)
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == order.company_id).first()
    return SalesOrderPublicResponse(order=_order_response(order), company=_company_branding(order.company, settings), can_confirm=False)
