from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from tenant_utils import get_current_company
from auth_utils import get_db, require_permission
from models import Company, Invoice, InvoicePayment, User
from schemas import (
    InvoiceOutstandingItem,
    InvoiceOutstandingListResponse,
    PaymentAgingBucket,
    PaymentListResponse,
    PaymentRecordItem,
    PaymentSummaryResponse,
)

router = APIRouter(prefix="/payments", tags=["payments"])




def _float(value) -> float:
    return float(value) if value is not None else 0.0


@router.get("/summary", response_model=PaymentSummaryResponse)
def payment_summary(
    user: User = Depends(require_permission("payments.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)

    now = datetime.now(timezone.utc)
    outstanding_statuses = ["issued", "sent", "viewed", "partially_paid", "overdue"]

    total_received = (
        db.query(func.coalesce(func.sum(InvoicePayment.amount), 0))
        .join(Invoice, InvoicePayment.invoice_id == Invoice.id)
        .filter(Invoice.company_id == company.id)
        .scalar()
    )

    outstanding_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(outstanding_statuses),
            Invoice.outstanding_amount > 0,
        )
        .all()
    )

    total_outstanding = sum(_float(i.outstanding_amount) for i in outstanding_invoices)
    overdue_count = sum(
        1 for i in outstanding_invoices
        if i.due_date and i.due_date < now and i.status != "paid"
    )

    payment_count = (
        db.query(func.count(InvoicePayment.id))
        .join(Invoice, InvoicePayment.invoice_id == Invoice.id)
        .filter(Invoice.company_id == company.id)
        .scalar()
    )

    buckets = [
        ("0-30 days", 0, 30),
        ("31-60 days", 31, 60),
        ("61-90 days", 61, 90),
        ("90+ days", 91, 9999),
    ]
    aging = []
    for label, min_days, max_days in buckets:
        amount = 0.0
        count = 0
        for inv in outstanding_invoices:
            if not inv.issue_date:
                continue
            age_days = (now - inv.issue_date).days
            if min_days <= age_days <= max_days:
                amount += _float(inv.outstanding_amount)
                count += 1
        aging.append(PaymentAgingBucket(label=label, count=count, amount=amount))

    return PaymentSummaryResponse(
        total_received=_float(total_received),
        total_outstanding=total_outstanding,
        invoice_count_outstanding=len(outstanding_invoices),
        invoice_count_overdue=overdue_count,
        payment_count=payment_count or 0,
        aging_buckets=aging,
    )


@router.get("", response_model=PaymentListResponse)
def list_payments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("payments.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(InvoicePayment)
        .join(Invoice, InvoicePayment.invoice_id == Invoice.id)
        .options(
            joinedload(InvoicePayment.invoice),
            joinedload(InvoicePayment.recorded_by),
        )
        .filter(Invoice.company_id == company.id)
    )

    total = query.count()
    payments = (
        query.order_by(InvoicePayment.payment_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = [
        PaymentRecordItem(
            id=p.id,
            invoice_id=p.invoice_id,
            invoice_number=p.invoice.invoice_number,
            invoice_title=p.invoice.title,
            client_name=p.invoice.client_name,
            client_org=p.invoice.client_org,
            contact_id=p.invoice.contact_id,
            amount=_float(p.amount),
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            reference=p.reference,
            note=p.note,
            recorded_by_name=p.recorded_by.name if p.recorded_by else None,
        )
        for p in payments
    ]
    return PaymentListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/outstanding", response_model=InvoiceOutstandingListResponse)
def list_outstanding(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    overdue_only: bool = False,
    user: User = Depends(require_permission("payments.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    now = datetime.now(timezone.utc)
    outstanding_statuses = ["issued", "sent", "viewed", "partially_paid", "overdue"]

    query = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(outstanding_statuses),
            Invoice.outstanding_amount > 0,
        )
    )
    if overdue_only:
        query = query.filter(Invoice.due_date < now)

    total = query.count()
    invoices = (
        query.order_by(Invoice.due_date.asc().nullslast())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = []
    for inv in invoices:
        age_days = (now - inv.issue_date).days if inv.issue_date else None
        items.append(
            InvoiceOutstandingItem(
                id=inv.id,
                invoice_number=inv.invoice_number,
                title=inv.title,
                client_name=inv.client_name,
                client_org=inv.client_org,
                contact_id=inv.contact_id,
                status=inv.status,
                grand_total=_float(inv.grand_total),
                amount_paid=_float(inv.amount_paid),
                outstanding_amount=_float(inv.outstanding_amount),
                issue_date=inv.issue_date,
                due_date=inv.due_date,
                is_overdue=bool(inv.due_date and inv.due_date < now),
                age_days=age_days,
            )
        )

    return InvoiceOutstandingListResponse(items=items, total=total, page=page, limit=limit)
