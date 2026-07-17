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
from company_branding import build_company_branding
from config import FRONTEND_URL, STAFF_ROLES
from models import (
    Company,
    Contact,
    Deal,
    Lead,
    Product,
    Quotation,
    QuotationLineItem,
    SystemSetting,
    User,
)
from quotation_config import (
    ALLOWED_TRANSITIONS,
    COMPANY_QUOTE_DOCUMENT_LABEL,
    COMPANY_QUOTE_PREPARED_BY,
    DEFAULT_BANK_INSTRUCTIONS,
    DEFAULT_BANK_PAYMENT_INTRO,
    DEFAULT_DELIVERABLES,
    DEFAULT_DOCUMENTS_CHECKLIST,
    DEFAULT_HOW_TO_GET_STARTED,
    DEFAULT_INVESTMENT_COMMISSION,
    DEFAULT_INVESTMENT_INCLUDES,
    DEFAULT_LEGAL_FOOTER,
    DEFAULT_PAYMENT_INSTALLMENTS,
    DEFAULT_PAYMENT_TERMS,
    DEFAULT_PROJECT_OVERVIEW,
    DEFAULT_SCOPE_NOTES,
    DEFAULT_TIMELINE_NOTES,
    DEFAULT_VALIDITY_CLAUSE,
    DEFAULT_WHY_CHOOSE_ITEMS,
    DISCOUNT_APPROVAL_THRESHOLD_PERCENT,
    EDITABLE_STATUSES,
    FINAL_STATUSES,
    QUOTATION_STATUS_LABELS,
    QUOTATION_STATUSES,
    VALUE_APPROVAL_THRESHOLD,
)
from services.document_number_service import generate_quote_number
from schemas import (
    QuotationApprovalRequest,
    QuotationClientActionRequest,
    QuotationCompanyBranding,
    QuotationCreateRequest,
    QuotationDefaultsResponse,
    QuotationLineItemFields,
    QuotationLineItemResponse,
    QuotationListResponse,
    QuotationPublicResponse,
    QuotationRejectRequest,
    QuotationResponse,
    QuotationSendRequest,
    QuotationStatsResponse,
    QuotationStatusOption,
    QuotationUpdateRequest,
    QuotationVersionSummary,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/quotations", tags=["quotations"])
public_router = APIRouter(prefix="/public/quotes", tags=["public-quotes"])



def _decimal(value: float | Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _float(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _validate_status(status: str) -> None:
    if status not in QUOTATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(QUOTATION_STATUSES)}",
        )


def _transition_status(quote: Quotation, new_status: str) -> None:
    _validate_status(new_status)
    allowed = ALLOWED_TRANSITIONS.get(quote.status, set())
    if new_status not in allowed and quote.status != new_status:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {quote.status} to {new_status}",
        )
    quote.status = new_status


def _get_quotation(db: Session, quote_id: int, company_id: int) -> Quotation:
    quote = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.assigned_to),
            joinedload(Quotation.created_by),
            joinedload(Quotation.approved_by),
            joinedload(Quotation.deal),
            joinedload(Quotation.lead),
            joinedload(Quotation.contact),
            joinedload(Quotation.line_items).joinedload(QuotationLineItem.product),
        )
        .filter(Quotation.id == quote_id, Quotation.company_id == company_id)
        .first()
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quote


def _get_quotation_by_token(db: Session, token: str) -> Quotation:
    quote = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.line_items).joinedload(QuotationLineItem.product),
            joinedload(Quotation.deal),
            joinedload(Quotation.lead),
            joinedload(Quotation.contact),
            joinedload(Quotation.company),
        )
        .filter(Quotation.share_token == token)
        .first()
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quote


def _validate_assigned_to(db: Session, assigned_to_id: int | None, company_id: int):
    if assigned_to_id is None:
        return
    staff = (
        db.query(User)
        .filter(
            User.id == assigned_to_id,
            User.company_id == company_id,
            User.role.in_(STAFF_ROLES),
            User.status == "active",
        )
        .first()
    )
    if not staff:
        raise HTTPException(status_code=400, detail="Invalid assigned staff member")


def _validate_deal(db: Session, deal_id: int | None, company_id: int):
    if deal_id is None:
        return
    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.company_id == company_id).first()
    if not deal:
        raise HTTPException(status_code=400, detail="Invalid deal")


def _validate_lead(db: Session, lead_id: int | None, company_id: int):
    if lead_id is None:
        return
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.company_id == company_id).first()
    if not lead:
        raise HTTPException(status_code=400, detail="Invalid lead")


def _validate_contact(db: Session, contact_id: int | None, company_id: int):
    if contact_id is None:
        return
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.company_id == company_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=400, detail="Invalid contact")


def _validate_product(db: Session, product_id: int | None, company_id: int):
    if product_id is None:
        return
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == company_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=400, detail="Invalid product")


def _compute_line(item: QuotationLineItemFields | dict) -> tuple[Decimal, Decimal, Decimal]:
    qty = _decimal(item.quantity if hasattr(item, "quantity") else item["quantity"])
    unit_price = _decimal(item.unit_price if hasattr(item, "unit_price") else item["unit_price"])
    discount_percent = _decimal(
        item.discount_percent if hasattr(item, "discount_percent") else item["discount_percent"]
    )
    discount_amount = _decimal(
        item.discount_amount if hasattr(item, "discount_amount") else item["discount_amount"]
    )
    tax_rate = _decimal(item.tax_rate if hasattr(item, "tax_rate") else item["tax_rate"])

    line_subtotal = qty * unit_price
    if discount_amount > 0:
        line_discount = discount_amount
    else:
        line_discount = line_subtotal * (discount_percent / Decimal("100"))
    after_discount = max(line_subtotal - line_discount, Decimal("0"))
    line_tax = after_discount * (tax_rate / Decimal("100"))
    line_total = after_discount + line_tax
    return line_subtotal, line_discount, line_total


def _compute_totals(
    line_items: list,
    header_discount_amount: float,
    header_discount_percent: float,
) -> dict[str, Decimal]:
    subtotal = Decimal("0")
    line_discount_total = Decimal("0")
    total_tax = Decimal("0")

    for item in line_items:
        qty = _decimal(item.quantity if hasattr(item, "quantity") else item["quantity"])
        unit_price = _decimal(item.unit_price if hasattr(item, "unit_price") else item["unit_price"])
        discount_percent = _decimal(
            item.discount_percent if hasattr(item, "discount_percent") else item["discount_percent"]
        )
        discount_amount = _decimal(
            item.discount_amount if hasattr(item, "discount_amount") else item["discount_amount"]
        )
        tax_rate = _decimal(item.tax_rate if hasattr(item, "tax_rate") else item["tax_rate"])

        line_subtotal = qty * unit_price
        if discount_amount > 0:
            line_discount = discount_amount
        else:
            line_discount = line_subtotal * (discount_percent / Decimal("100"))
        after_discount = max(line_subtotal - line_discount, Decimal("0"))
        line_tax = after_discount * (tax_rate / Decimal("100"))

        subtotal += line_subtotal
        line_discount_total += line_discount
        total_tax += line_tax

    after_line_discounts = max(subtotal - line_discount_total, Decimal("0"))
    hdr_amount = _decimal(header_discount_amount)
    hdr_percent = _decimal(header_discount_percent)
    if hdr_amount > 0:
        header_discount = hdr_amount
    else:
        header_discount = after_line_discounts * (hdr_percent / Decimal("100"))

    taxable = max(after_line_discounts - header_discount, Decimal("0"))
    if after_line_discounts > 0:
        tax_scale = taxable / after_line_discounts
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


def _requires_approval(header_discount_percent: float, grand_total: float) -> bool:
    return (
        header_discount_percent > DISCOUNT_APPROVAL_THRESHOLD_PERCENT
        or grand_total > VALUE_APPROVAL_THRESHOLD
    )


def _generate_quote_number(db: Session, company: Company) -> str:
    return generate_quote_number(db, company)


def _line_item_to_response(item: QuotationLineItem) -> QuotationLineItemResponse:
    return QuotationLineItemResponse(
        id=item.id,
        product_id=item.product_id,
        product_name=item.product.name if item.product else None,
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
    )


def _quotation_to_response(quote: Quotation) -> QuotationResponse:
    share_url = None
    if quote.share_token:
        share_url = f"{FRONTEND_URL}/quote/{quote.share_token}"

    return QuotationResponse(
        id=quote.id,
        company_id=quote.company_id,
        quote_number=quote.quote_number,
        title=quote.title,
        status=quote.status,
        version=quote.version,
        currency=quote.currency,
        quote_date=quote.quote_date,
        valid_until=quote.valid_until,
        deal_id=quote.deal_id,
        deal_title=quote.deal.title if quote.deal else None,
        lead_id=quote.lead_id,
        lead_name=quote.lead.name if quote.lead else None,
        contact_id=quote.contact_id,
        contact_name=quote.contact.name if quote.contact else None,
        assigned_to_id=quote.assigned_to_id,
        assigned_to_name=quote.assigned_to.name if quote.assigned_to else None,
        created_by_id=quote.created_by_id,
        created_by_name=quote.created_by.name if quote.created_by else None,
        approved_by_id=quote.approved_by_id,
        approved_by_name=quote.approved_by.name if quote.approved_by else None,
        parent_quote_id=quote.parent_quote_id,
        root_quote_id=quote.root_quote_id,
        client_name=quote.client_name,
        client_email=quote.client_email,
        client_org=quote.client_org,
        attention_to=quote.attention_to,
        billing_address=quote.billing_address,
        shipping_address=quote.shipping_address,
        subtotal=_float(quote.subtotal),
        line_discount_total=_float(quote.line_discount_total),
        header_discount_amount=_float(quote.header_discount_amount),
        header_discount_percent=_float(quote.header_discount_percent),
        total_tax=_float(quote.total_tax),
        grand_total=_float(quote.grand_total),
        scope_notes=quote.scope_notes,
        deliverables=quote.deliverables,
        timeline_notes=quote.timeline_notes,
        payment_terms=quote.payment_terms,
        validity_clause=quote.validity_clause,
        cancellation_clause=quote.cancellation_clause,
        legal_footer=quote.legal_footer,
        internal_notes=quote.internal_notes,
        approval_comments=quote.approval_comments,
        requires_approval=bool(quote.requires_approval),
        share_token=quote.share_token,
        share_url=share_url,
        sent_at=quote.sent_at,
        viewed_at=quote.viewed_at,
        accepted_at=quote.accepted_at,
        rejected_at=quote.rejected_at,
        approved_at=quote.approved_at,
        cancelled_at=quote.cancelled_at,
        client_rejection_reason=quote.client_rejection_reason,
        line_items=[_line_item_to_response(li) for li in quote.line_items],
        created_at=quote.created_at,
        updated_at=quote.updated_at,
    )


def _company_branding(company: Company, settings: SystemSetting | None) -> QuotationCompanyBranding:
    return build_company_branding(company, settings, for_invoice=False)


def _is_expired(quote: Quotation) -> bool:
    if quote.valid_until is None:
        return False
    now = datetime.now(timezone.utc)
    valid = quote.valid_until
    if valid.tzinfo is None:
        valid = valid.replace(tzinfo=timezone.utc)
    return now > valid


def _check_expiry(quote: Quotation) -> None:
    if _is_expired(quote) and quote.status in {"sent", "viewed", "negotiation"}:
        quote.status = "expired"


def _apply_line_items(quote: Quotation, line_items: list, db: Session) -> None:
    quote.line_items.clear()
    for idx, item in enumerate(line_items):
        _validate_product(db, item.product_id, quote.company_id)
        line_subtotal, line_discount, line_total = _compute_line(item)
        quote.line_items.append(
            QuotationLineItem(
                product_id=item.product_id,
                sort_order=item.sort_order if item.sort_order else idx,
                section=item.section,
                item_name=item.item_name.strip(),
                description=item.description,
                quantity=_decimal(item.quantity),
                unit=item.unit or "Service",
                unit_price=_decimal(item.unit_price),
                discount_percent=_decimal(item.discount_percent),
                discount_amount=_decimal(item.discount_amount),
                tax_rate=_decimal(item.tax_rate),
                line_subtotal=line_subtotal,
                line_total=line_total,
            )
        )


def _populate_from_context(
    db: Session,
    company_id: int,
    payload: QuotationCreateRequest,
) -> QuotationCreateRequest:
    data = payload.model_dump()
    if payload.contact_id:
        contact = (
            db.query(Contact)
            .filter(Contact.id == payload.contact_id, Contact.company_id == company_id)
            .first()
        )
        if contact:
            data.setdefault("client_name", contact.name)
            data.setdefault("client_email", contact.email)
            data.setdefault("client_org", contact.organization_name)
            if not data.get("billing_address"):
                parts = [
                    contact.address_line1,
                    contact.address_line2,
                    contact.city,
                    contact.state,
                    contact.pincode,
                    contact.country,
                ]
                data["billing_address"] = ", ".join(p for p in parts if p)
    if payload.lead_id and not data.get("client_name"):
        lead = (
            db.query(Lead)
            .filter(Lead.id == payload.lead_id, Lead.company_id == company_id)
            .first()
        )
        if lead:
            data.setdefault("client_name", lead.name)
            data.setdefault("client_email", lead.email)
            data.setdefault("client_org", lead.organization_name)
    return QuotationCreateRequest(**data)


def _build_quotation(
    db: Session,
    company: Company,
    payload: QuotationCreateRequest,
    user: User,
    *,
    quote_number: str | None = None,
    version: int = 1,
    parent_quote_id: int | None = None,
    root_quote_id: int | None = None,
) -> Quotation:
    _validate_assigned_to(db, payload.assigned_to_id, company.id)
    _validate_deal(db, payload.deal_id, company.id)
    _validate_lead(db, payload.lead_id, company.id)
    _validate_contact(db, payload.contact_id, company.id)

    for item in payload.line_items:
        _validate_product(db, item.product_id, company.id)

    if payload.valid_until and payload.quote_date:
        if payload.valid_until < payload.quote_date:
            raise HTTPException(
                status_code=400,
                detail="Valid until date must be on or after quote date",
            )

    totals = _compute_totals(
        payload.line_items,
        payload.header_discount_amount,
        payload.header_discount_percent,
    )
    needs_approval = _requires_approval(
        float(totals["header_discount_percent"]),
        float(totals["grand_total"]),
    )

    quote = Quotation(
        company_id=company.id,
        created_by_id=user.id,
        quote_number=quote_number or _generate_quote_number(db, company),
        title=payload.title.strip(),
        status="draft",
        version=version,
        currency=payload.currency or company.currency or "INR",
        quote_date=payload.quote_date or datetime.now(timezone.utc),
        valid_until=payload.valid_until,
        deal_id=payload.deal_id,
        lead_id=payload.lead_id,
        contact_id=payload.contact_id,
        assigned_to_id=payload.assigned_to_id or user.id,
        client_name=payload.client_name,
        client_email=payload.client_email,
        client_org=payload.client_org,
        attention_to=payload.attention_to,
        billing_address=payload.billing_address,
        shipping_address=payload.shipping_address,
        subtotal=totals["subtotal"],
        line_discount_total=totals["line_discount_total"],
        header_discount_amount=totals["header_discount_amount"],
        header_discount_percent=totals["header_discount_percent"],
        total_tax=totals["total_tax"],
        grand_total=totals["grand_total"],
        scope_notes=payload.scope_notes,
        deliverables=payload.deliverables,
        timeline_notes=payload.timeline_notes,
        payment_terms=payload.payment_terms or DEFAULT_PAYMENT_TERMS,
        validity_clause=payload.validity_clause or DEFAULT_VALIDITY_CLAUSE,
        cancellation_clause=payload.cancellation_clause,
        legal_footer=payload.legal_footer or DEFAULT_LEGAL_FOOTER,
        internal_notes=payload.internal_notes,
        requires_approval=1 if needs_approval else 0,
        parent_quote_id=parent_quote_id,
        root_quote_id=root_quote_id,
    )
    db.add(quote)
    db.flush()
    _apply_line_items(quote, payload.line_items, db)
    return quote


def _update_quotation_fields(quote: Quotation, payload: QuotationUpdateRequest, db: Session):
    if quote.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Only draft, pending approval, or approved quotations can be edited",
        )

    _validate_assigned_to(db, payload.assigned_to_id, quote.company_id)
    _validate_deal(db, payload.deal_id, quote.company_id)
    _validate_lead(db, payload.lead_id, quote.company_id)
    _validate_contact(db, payload.contact_id, quote.company_id)
    for item in payload.line_items:
        _validate_product(db, item.product_id, quote.company_id)

    if payload.valid_until and payload.quote_date:
        if payload.valid_until < payload.quote_date:
            raise HTTPException(
                status_code=400,
                detail="Valid until date must be on or after quote date",
            )

    totals = _compute_totals(
        payload.line_items,
        payload.header_discount_amount,
        payload.header_discount_percent,
    )
    needs_approval = _requires_approval(
        float(totals["header_discount_percent"]),
        float(totals["grand_total"]),
    )

    quote.title = payload.title.strip()
    quote.currency = payload.currency or quote.currency
    quote.quote_date = payload.quote_date
    quote.valid_until = payload.valid_until
    quote.deal_id = payload.deal_id
    quote.lead_id = payload.lead_id
    quote.contact_id = payload.contact_id
    quote.assigned_to_id = payload.assigned_to_id
    quote.client_name = payload.client_name
    quote.client_email = payload.client_email
    quote.client_org = payload.client_org
    quote.attention_to = payload.attention_to
    quote.billing_address = payload.billing_address
    quote.shipping_address = payload.shipping_address
    quote.subtotal = totals["subtotal"]
    quote.line_discount_total = totals["line_discount_total"]
    quote.header_discount_amount = totals["header_discount_amount"]
    quote.header_discount_percent = totals["header_discount_percent"]
    quote.total_tax = totals["total_tax"]
    quote.grand_total = totals["grand_total"]
    quote.scope_notes = payload.scope_notes
    quote.deliverables = payload.deliverables
    quote.timeline_notes = payload.timeline_notes
    quote.payment_terms = payload.payment_terms
    quote.validity_clause = payload.validity_clause
    quote.cancellation_clause = payload.cancellation_clause
    quote.legal_footer = payload.legal_footer
    quote.internal_notes = payload.internal_notes
    quote.requires_approval = 1 if needs_approval else 0

    _apply_line_items(quote, payload.line_items, db)


@router.get("/statuses", response_model=list[QuotationStatusOption])
def quotation_statuses(
    _: User = Depends(require_permission("quotations.view")),
):
    return [
        QuotationStatusOption(value=s, label=QUOTATION_STATUS_LABELS[s])
        for s in QUOTATION_STATUSES
    ]


@router.get("/defaults", response_model=QuotationDefaultsResponse)
def quotation_defaults(
    _: User = Depends(require_permission("quotations.view")),
):
    return QuotationDefaultsResponse(
        scope_notes=DEFAULT_SCOPE_NOTES,
        project_overview=DEFAULT_PROJECT_OVERVIEW,
        deliverables=DEFAULT_DELIVERABLES,
        timeline_notes=DEFAULT_TIMELINE_NOTES,
        payment_terms=DEFAULT_PAYMENT_TERMS,
        investment_commission=DEFAULT_INVESTMENT_COMMISSION,
        investment_includes=DEFAULT_INVESTMENT_INCLUDES,
        payment_installments=DEFAULT_PAYMENT_INSTALLMENTS,
        bank_instructions=DEFAULT_BANK_INSTRUCTIONS,
        bank_payment_intro=DEFAULT_BANK_PAYMENT_INTRO,
        how_to_get_started=DEFAULT_HOW_TO_GET_STARTED,
        why_choose_items=DEFAULT_WHY_CHOOSE_ITEMS,
        validity_clause=DEFAULT_VALIDITY_CLAUSE,
        legal_footer=DEFAULT_LEGAL_FOOTER,
        documents_checklist=DEFAULT_DOCUMENTS_CHECKLIST,
        prepared_by_label=COMPANY_QUOTE_PREPARED_BY,
        document_subtitle=COMPANY_QUOTE_DOCUMENT_LABEL,
    )


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def quotation_assignees(
    user: User = Depends(require_permission("quotations.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    staff = (
        db.query(User)
        .filter(
            User.company_id == company.id,
            User.role.in_(STAFF_ROLES),
            User.status == "active",
        )
        .order_by(User.name)
        .all()
    )
    return [
        StaffAssigneeResponse(id=u.id, name=u.name, email=u.email, role=u.role)
        for u in staff
    ]


@router.get("/stats/summary", response_model=QuotationStatsResponse)
def quotation_stats(
    user: User = Depends(require_permission("quotations.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    rows = (
        db.query(Quotation.status, func.count(Quotation.id))
        .filter(Quotation.company_id == company.id)
        .group_by(Quotation.status)
        .all()
    )
    counts = {status: 0 for status in QUOTATION_STATUSES}
    for status, count in rows:
        counts[status] = count

    total_value = (
        db.query(func.coalesce(func.sum(Quotation.grand_total), 0))
        .filter(
            Quotation.company_id == company.id,
            Quotation.status.notin_(list(FINAL_STATUSES)),
        )
        .scalar()
    )
    accepted_value = (
        db.query(func.coalesce(func.sum(Quotation.grand_total), 0))
        .filter(Quotation.company_id == company.id, Quotation.status == "accepted")
        .scalar()
    )

    soon = datetime.now(timezone.utc) + timedelta(days=7)
    expiring_soon = (
        db.query(func.count(Quotation.id))
        .filter(
            Quotation.company_id == company.id,
            Quotation.valid_until.isnot(None),
            Quotation.valid_until <= soon,
            Quotation.status.in_(["sent", "viewed", "negotiation", "approved"]),
        )
        .scalar()
    )

    return QuotationStatsResponse(
        total=sum(counts.values()),
        draft=counts["draft"],
        pending_approval=counts["pending_approval"],
        approved=counts["approved"],
        sent=counts["sent"],
        viewed=counts["viewed"],
        negotiation=counts["negotiation"],
        accepted=counts["accepted"],
        rejected=counts["rejected"],
        expired=counts["expired"],
        cancelled=counts["cancelled"],
        total_value=float(total_value or 0),
        accepted_value=float(accepted_value or 0),
        expiring_soon=expiring_soon or 0,
    )


@router.get("/approval-queue", response_model=QuotationListResponse)
def approval_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("quotations.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.assigned_to),
            joinedload(Quotation.created_by),
            joinedload(Quotation.deal),
            joinedload(Quotation.lead),
            joinedload(Quotation.contact),
            joinedload(Quotation.line_items),
        )
        .filter(
            Quotation.company_id == company.id,
            Quotation.status == "pending_approval",
        )
        .order_by(Quotation.updated_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return QuotationListResponse(
        items=[_quotation_to_response(q) for q in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("", response_model=QuotationListResponse)
def list_quotations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    search: str | None = None,
    owner_id: int | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    expiring_in_days: int | None = None,
    sort_by: str = Query("updated_at"),
    sort_dir: str = Query("desc"),
    user: User = Depends(require_permission("quotations.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.assigned_to),
            joinedload(Quotation.created_by),
            joinedload(Quotation.deal),
            joinedload(Quotation.lead),
            joinedload(Quotation.contact),
            joinedload(Quotation.line_items),
        )
        .filter(Quotation.company_id == company.id)
    )

    if status:
        _validate_status(status)
        query = query.filter(Quotation.status == status)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Quotation.quote_number.ilike(term),
                Quotation.title.ilike(term),
                Quotation.client_name.ilike(term),
                Quotation.client_org.ilike(term),
            )
        )

    if owner_id:
        query = query.filter(Quotation.assigned_to_id == owner_id)

    if amount_min is not None:
        query = query.filter(Quotation.grand_total >= amount_min)
    if amount_max is not None:
        query = query.filter(Quotation.grand_total <= amount_max)

    if expiring_in_days is not None:
        cutoff = datetime.now(timezone.utc) + timedelta(days=expiring_in_days)
        query = query.filter(
            Quotation.valid_until.isnot(None),
            Quotation.valid_until <= cutoff,
            Quotation.status.in_(["sent", "viewed", "negotiation", "approved"]),
        )

    sort_column = {
        "updated_at": Quotation.updated_at,
        "grand_total": Quotation.grand_total,
        "valid_until": Quotation.valid_until,
    }.get(sort_by, Quotation.updated_at)
    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    for q in items:
        _check_expiry(q)
    db.commit()

    return QuotationListResponse(
        items=[_quotation_to_response(q) for q in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=QuotationResponse, status_code=201)
def create_quotation(
    payload: QuotationCreateRequest,
    request: Request,
    user: User = Depends(require_permission("quotations.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    enriched = _populate_from_context(db, company.id, payload)
    quote = _build_quotation(db, company, enriched, user)
    db.commit()
    db.refresh(quote)
    quote = _get_quotation(db, quote.id, company.id)

    log_activity(
        db,
        "quote_created",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} created",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.get("/{quote_id}", response_model=QuotationResponse)
def get_quotation(
    quote_id: int,
    user: User = Depends(require_permission("quotations.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    _check_expiry(quote)
    db.commit()
    return _quotation_to_response(quote)


@router.put("/{quote_id}", response_model=QuotationResponse)
def update_quotation(
    quote_id: int,
    payload: QuotationUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("quotations.edit_draft")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    _update_quotation_fields(quote, payload, db)
    db.commit()
    quote = _get_quotation(db, quote_id, company.id)

    log_activity(
        db,
        "quote_saved_draft",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} updated",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.delete("/{quote_id}", status_code=204)
def delete_quotation(
    quote_id: int,
    user: User = Depends(require_permission("quotations.edit_draft")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft quotations can be deleted")
    db.delete(quote)
    db.commit()


@router.post("/{quote_id}/submit-approval", response_model=QuotationResponse)
def submit_for_approval(
    quote_id: int,
    request: Request,
    user: User = Depends(require_permission("quotations.submit_approval")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft quotations can be submitted")
    if not quote.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")

    if quote.requires_approval:
        _transition_status(quote, "pending_approval")
    else:
        _transition_status(quote, "approved")
        quote.approved_at = datetime.now(timezone.utc)
        quote.approved_by_id = user.id

    db.commit()
    quote = _get_quotation(db, quote_id, company.id)
    log_activity(
        db,
        "quote_submitted_approval",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} submitted for approval",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.post("/{quote_id}/approve", response_model=QuotationResponse)
def approve_quotation(
    quote_id: int,
    payload: QuotationApprovalRequest,
    request: Request,
    user: User = Depends(require_permission("quotations.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Quotation is not awaiting approval")
    _transition_status(quote, "approved")
    quote.approved_at = datetime.now(timezone.utc)
    quote.approved_by_id = user.id
    quote.approval_comments = payload.comments
    db.commit()
    quote = _get_quotation(db, quote_id, company.id)
    log_activity(
        db,
        "quote_approved",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} approved",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.post("/{quote_id}/reject-approval", response_model=QuotationResponse)
def reject_approval(
    quote_id: int,
    payload: QuotationRejectRequest,
    request: Request,
    user: User = Depends(require_permission("quotations.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Quotation is not awaiting approval")
    _transition_status(quote, "draft")
    quote.approval_comments = payload.comments
    db.commit()
    quote = _get_quotation(db, quote_id, company.id)
    log_activity(
        db,
        "quote_rejected_by_approver",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} rejected by approver",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.post("/{quote_id}/send", response_model=QuotationResponse)
def send_quotation(
    quote_id: int,
    payload: QuotationSendRequest,
    request: Request,
    user: User = Depends(require_permission("quotations.send")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status not in {"approved", "sent", "viewed", "negotiation"}:
        raise HTTPException(
            status_code=400,
            detail="Quotation must be approved before sending",
        )
    if not quote.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    if not quote.payment_terms or not quote.validity_clause:
        raise HTTPException(
            status_code=400,
            detail="Payment terms and validity clause are required before sending",
        )

    if not quote.share_token:
        quote.share_token = secrets.token_urlsafe(32)

    recipient = payload.recipient_email or quote.client_email
    if not recipient:
        raise HTTPException(status_code=400, detail="Client email is required to send quote")

    quote.client_email = recipient
    if quote.status == "approved":
        _transition_status(quote, "sent")
    quote.sent_at = datetime.now(timezone.utc)
    db.commit()
    quote = _get_quotation(db, quote_id, company.id)

    share_url = f"{FRONTEND_URL}/quote/{quote.share_token}"
    try:
        from services.email_service import render_template, send_email

        html = render_template(
            "quote_sent.html",
            company_name=company.display_name,
            quote_number=quote.quote_number,
            quote_title=quote.title,
            client_name=quote.client_name or "Client",
            grand_total=f"{quote.currency} {_float(quote.grand_total):,.2f}",
            valid_until=quote.valid_until.strftime("%d %b %Y") if quote.valid_until else "N/A",
            share_url=share_url,
            message=payload.message or "",
        )
        send_email(
            recipient,
            f"Quotation {quote.quote_number} from {company.display_name}",
            html,
        )
    except Exception:
        pass

    log_activity(
        db,
        "quote_sent",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} sent to {recipient}",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.post("/{quote_id}/cancel", response_model=QuotationResponse)
def cancel_quotation(
    quote_id: int,
    request: Request,
    user: User = Depends(require_permission("quotations.cancel")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status in FINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Quotation is already in a final state")
    quote.status = "cancelled"
    quote.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    quote = _get_quotation(db, quote_id, company.id)
    log_activity(
        db,
        "quote_cancelled",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} cancelled",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.post("/{quote_id}/revision", response_model=QuotationResponse, status_code=201)
def create_revision(
    quote_id: int,
    request: Request,
    user: User = Depends(require_permission("quotations.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    original = _get_quotation(db, quote_id, company.id)
    if original.status in {"draft", "pending_approval"}:
        raise HTTPException(
            status_code=400,
            detail="Cannot create revision from draft or pending approval quote",
        )

    root_id = original.root_quote_id or original.id
    max_version = (
        db.query(func.max(Quotation.version))
        .filter(
            Quotation.company_id == company.id,
            or_(
                Quotation.root_quote_id == root_id,
                Quotation.id == root_id,
            ),
        )
        .scalar()
    ) or original.version

    payload = QuotationCreateRequest(
        title=original.title,
        currency=original.currency,
        quote_date=datetime.now(timezone.utc),
        valid_until=(
            original.valid_until + timedelta(days=30)
            if original.valid_until
            else datetime.now(timezone.utc) + timedelta(days=30)
        ),
        deal_id=original.deal_id,
        lead_id=original.lead_id,
        contact_id=original.contact_id,
        assigned_to_id=original.assigned_to_id,
        client_name=original.client_name,
        client_email=original.client_email,
        client_org=original.client_org,
        attention_to=original.attention_to,
        billing_address=original.billing_address,
        shipping_address=original.shipping_address,
        header_discount_amount=_float(original.header_discount_amount),
        header_discount_percent=_float(original.header_discount_percent),
        scope_notes=original.scope_notes,
        deliverables=original.deliverables,
        timeline_notes=original.timeline_notes,
        payment_terms=original.payment_terms,
        validity_clause=original.validity_clause,
        cancellation_clause=original.cancellation_clause,
        legal_footer=original.legal_footer,
        internal_notes=original.internal_notes,
        line_items=[
            QuotationLineItemFields(
                product_id=li.product_id,
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
    )

    new_number = f"{original.quote_number}-V{max_version + 1}"
    revision = _build_quotation(
        db,
        company,
        payload,
        user,
        quote_number=new_number,
        version=max_version + 1,
        parent_quote_id=original.id,
        root_quote_id=root_id,
    )
    db.commit()
    revision = _get_quotation(db, revision.id, company.id)
    log_activity(
        db,
        "quote_revision_created",
        user_id=user.id,
        email=user.email,
        details=f"Revision {revision.quote_number} created from {original.quote_number}",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(revision)


@router.post("/{quote_id}/reminder", response_model=QuotationResponse)
def send_reminder(
    quote_id: int,
    request: Request,
    user: User = Depends(require_permission("quotations.send")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status not in {"sent", "viewed", "negotiation"}:
        raise HTTPException(status_code=400, detail="Reminders can only be sent for active quotes")
    if not quote.share_token or not quote.client_email:
        raise HTTPException(status_code=400, detail="Quote has not been sent to a client yet")

    share_url = f"{FRONTEND_URL}/quote/{quote.share_token}"
    try:
        from services.email_service import render_template, send_email

        html = render_template(
            "quote_sent.html",
            company_name=company.display_name,
            quote_number=quote.quote_number,
            quote_title=quote.title,
            client_name=quote.client_name or "Client",
            grand_total=f"{quote.currency} {_float(quote.grand_total):,.2f}",
            valid_until=quote.valid_until.strftime("%d %b %Y") if quote.valid_until else "N/A",
            share_url=share_url,
            message="This is a friendly reminder about your pending quotation.",
        )
        send_email(
            quote.client_email,
            f"Reminder: Quotation {quote.quote_number} from {company.display_name}",
            html,
        )
    except Exception:
        pass

    log_activity(
        db,
        "quote_reminder_sent",
        user_id=user.id,
        email=user.email,
        details=f"Reminder sent for {quote.quote_number}",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.post("/{quote_id}/accept-override", response_model=QuotationResponse)
def accept_override(
    quote_id: int,
    request: Request,
    user: User = Depends(require_permission("quotations.accept_override")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status in FINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Quotation is already finalized")
    if _is_expired(quote):
        raise HTTPException(status_code=400, detail="Expired quotations cannot be accepted")
    quote.status = "accepted"
    quote.accepted_at = datetime.now(timezone.utc)
    db.commit()
    quote = _get_quotation(db, quote_id, company.id)
    log_activity(
        db,
        "quote_accepted_by_client",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} marked accepted (internal)",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.post("/{quote_id}/reject-override", response_model=QuotationResponse)
def reject_override(
    quote_id: int,
    payload: QuotationRejectRequest,
    request: Request,
    user: User = Depends(require_permission("quotations.accept_override")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    if quote.status in FINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Quotation is already finalized")
    quote.status = "rejected"
    quote.rejected_at = datetime.now(timezone.utc)
    quote.client_rejection_reason = payload.comments
    db.commit()
    quote = _get_quotation(db, quote_id, company.id)
    log_activity(
        db,
        "quote_rejected_by_client",
        user_id=user.id,
        email=user.email,
        details=f"Quotation {quote.quote_number} marked rejected (internal)",
        ip_address=get_client_ip(request),
    )
    return _quotation_to_response(quote)


@router.get("/{quote_id}/versions", response_model=list[QuotationVersionSummary])
def list_versions(
    quote_id: int,
    user: User = Depends(require_permission("quotations.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    quote = _get_quotation(db, quote_id, company.id)
    root_id = quote.root_quote_id or quote.id
    versions = (
        db.query(Quotation)
        .filter(
            Quotation.company_id == company.id,
            or_(
                Quotation.id == root_id,
                Quotation.root_quote_id == root_id,
            ),
        )
        .order_by(Quotation.version.asc())
        .all()
    )
    return [
        QuotationVersionSummary(
            id=v.id,
            quote_number=v.quote_number,
            version=v.version,
            status=v.status,
            grand_total=_float(v.grand_total),
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in versions
    ]


# --- Public client-facing endpoints ---


@public_router.get("/{token}", response_model=QuotationPublicResponse)
def public_view_quote(token: str, db: Session = Depends(get_db)):
    quote = _get_quotation_by_token(db, token)
    _check_expiry(quote)
    db.commit()

    settings = (
        db.query(SystemSetting)
        .filter(SystemSetting.company_id == quote.company_id)
        .first()
    )
    expired = _is_expired(quote)
    can_accept = quote.status in {"sent", "viewed", "negotiation"} and not expired

    return QuotationPublicResponse(
        quote=_quotation_to_response(quote),
        company=_company_branding(quote.company, settings),
        is_expired=expired,
        can_accept=can_accept,
    )


@public_router.post("/{token}/view", response_model=QuotationPublicResponse)
def public_mark_viewed(token: str, db: Session = Depends(get_db)):
    quote = _get_quotation_by_token(db, token)
    if quote.status == "sent":
        quote.status = "viewed"
    if quote.viewed_at is None:
        quote.viewed_at = datetime.now(timezone.utc)
    db.commit()
    quote = _get_quotation_by_token(db, token)

    settings = (
        db.query(SystemSetting)
        .filter(SystemSetting.company_id == quote.company_id)
        .first()
    )
    expired = _is_expired(quote)
    can_accept = quote.status in {"sent", "viewed", "negotiation"} and not expired

    return QuotationPublicResponse(
        quote=_quotation_to_response(quote),
        company=_company_branding(quote.company, settings),
        is_expired=expired,
        can_accept=can_accept,
    )


@public_router.post("/{token}/accept", response_model=QuotationPublicResponse)
def public_accept_quote(token: str, db: Session = Depends(get_db)):
    quote = _get_quotation_by_token(db, token)
    if _is_expired(quote):
        raise HTTPException(status_code=400, detail="This quotation has expired")
    if quote.status not in {"sent", "viewed", "negotiation"}:
        raise HTTPException(status_code=400, detail="This quotation cannot be accepted")
    quote.status = "accepted"
    quote.accepted_at = datetime.now(timezone.utc)
    db.commit()
    quote = _get_quotation_by_token(db, token)

    settings = (
        db.query(SystemSetting)
        .filter(SystemSetting.company_id == quote.company_id)
        .first()
    )
    return QuotationPublicResponse(
        quote=_quotation_to_response(quote),
        company=_company_branding(quote.company, settings),
        is_expired=False,
        can_accept=False,
    )


@public_router.post("/{token}/reject", response_model=QuotationPublicResponse)
def public_reject_quote(
    token: str,
    payload: QuotationClientActionRequest,
    db: Session = Depends(get_db),
):
    quote = _get_quotation_by_token(db, token)
    if quote.status not in {"sent", "viewed", "negotiation"}:
        raise HTTPException(status_code=400, detail="This quotation cannot be rejected")
    quote.status = "rejected"
    quote.rejected_at = datetime.now(timezone.utc)
    quote.client_rejection_reason = payload.reason
    db.commit()
    quote = _get_quotation_by_token(db, token)

    settings = (
        db.query(SystemSetting)
        .filter(SystemSetting.company_id == quote.company_id)
        .first()
    )
    return QuotationPublicResponse(
        quote=_quotation_to_response(quote),
        company=_company_branding(quote.company, settings),
        is_expired=_is_expired(quote),
        can_accept=False,
    )


@public_router.post("/{token}/request-changes", response_model=QuotationPublicResponse)
def public_request_changes(
    token: str,
    payload: QuotationClientActionRequest,
    db: Session = Depends(get_db),
):
    quote = _get_quotation_by_token(db, token)
    if quote.status not in {"sent", "viewed", "negotiation"}:
        raise HTTPException(status_code=400, detail="Cannot request changes on this quotation")
    quote.status = "negotiation"
    if payload.message:
        note = f"Client requested changes: {payload.message}"
        quote.internal_notes = (
            f"{quote.internal_notes}\n\n{note}" if quote.internal_notes else note
        )
    db.commit()
    quote = _get_quotation_by_token(db, token)

    settings = (
        db.query(SystemSetting)
        .filter(SystemSetting.company_id == quote.company_id)
        .first()
    )
    return QuotationPublicResponse(
        quote=_quotation_to_response(quote),
        company=_company_branding(quote.company, settings),
        is_expired=_is_expired(quote),
        can_accept=False,
    )
