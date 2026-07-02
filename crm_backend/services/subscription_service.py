"""Subscription Management business logic (Phase 1)."""

from __future__ import annotations

import calendar
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from invoice_config import DEFAULT_BANK_INSTRUCTIONS, DEFAULT_BILLING_NOTES, DEFAULT_PAYMENT_TERMS
from models import (
    Company,
    Contact,
    CustomerSubscription,
    Invoice,
    InvoiceLineItem,
    SubscriptionInvoice,
    SubscriptionPlan,
    SubscriptionPlanChange,
    SubscriptionSettings,
    User,
)
from services.document_number_service import generate_invoice_number
from services.notification_service import notify_role
from subscriptions_config import BILLABLE_STATUSES, BILLING_INTERVALS, CHANGE_TYPES, PLAN_STATUSES


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_interval(d: date, interval: str, interval_days: int | None = None) -> date:
    if interval == "monthly":
        return _add_months(d, 1)
    if interval == "quarterly":
        return _add_months(d, 3)
    if interval == "yearly":
        return date(d.year + 1, d.month, min(d.day, calendar.monthrange(d.year + 1, d.month)[1]))
    if interval == "custom_days":
        return d + timedelta(days=interval_days or 30)
    return _add_months(d, 1)


def period_end(period_start: date, interval: str, interval_days: int | None = None) -> date:
    return add_interval(period_start, interval, interval_days) - timedelta(days=1)


def unit_price(sub: CustomerSubscription, plan: SubscriptionPlan) -> Decimal:
    if sub.unit_price is not None:
        return Decimal(str(sub.unit_price))
    return Decimal(str(plan.price))


def mrr_for_subscription(sub: CustomerSubscription, plan: SubscriptionPlan | None = None) -> float:
    if sub.status not in ("active", "trialing", "past_due"):
        return 0.0
    plan = plan or sub.plan
    if not plan:
        return 0.0
    price = _float(unit_price(sub, plan)) * int(sub.quantity or 1)
    interval = plan.billing_interval
    if interval == "yearly":
        return price / 12
    if interval == "quarterly":
        return price / 3
    if interval == "custom_days":
        days = plan.interval_days or 30
        return price * 30 / days if days > 0 else price
    return price


def generate_subscription_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    pattern = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(CustomerSubscription.id))
        .filter(
            CustomerSubscription.company_id == company_id,
            CustomerSubscription.subscription_number.like(pattern),
        )
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _contact_billing(contact: Contact) -> dict:
    parts = [contact.address_line1, contact.address_line2, contact.city, contact.state, contact.pincode]
    return {
        "client_name": contact.name,
        "client_email": contact.email,
        "client_phone": contact.phone,
        "client_org": contact.organization_name,
        "client_gstin": contact.gstin,
        "billing_address": ", ".join(p for p in parts if p) or None,
    }


def _invoice_line_amounts(qty: float, price: float, gst_rate: float) -> tuple[Decimal, Decimal, Decimal]:
    line_subtotal = Decimal(str(qty * price))
    tax = line_subtotal * Decimal(str(gst_rate)) / Decimal("100")
    line_total = line_subtotal + tax
    return line_subtotal, tax, line_total


def create_subscription_invoice(
    db: Session,
    company: Company,
    user: User,
    sub: CustomerSubscription,
    plan: SubscriptionPlan,
    settings: SubscriptionSettings,
    period_start: date,
    period_end_date: date,
) -> Invoice:
    contact = sub.contact
    qty = int(sub.quantity or 1)
    price = _float(unit_price(sub, plan))
    gst = _float(plan.gst_rate)
    line_subtotal, tax_amt, line_total = _invoice_line_amounts(qty, price, gst)
    subtotal = line_subtotal
    total_tax = tax_amt
    grand_total = line_total

    issue_mode = settings.auto_invoice_mode or "draft"
    status = "issued" if issue_mode == "issue" else "draft"
    now = _utcnow()
    billing = _contact_billing(contact) if contact else {}

    inv = Invoice(
        company_id=company.id,
        created_by_id=user.id,
        issued_by_id=user.id if status == "issued" else None,
        contact_id=sub.contact_id,
        title=f"Subscription {sub.subscription_number} — {plan.name}",
        status=status,
        invoice_type="standard",
        source_type="manual",
        currency=plan.currency or company.currency or "INR",
        issue_date=now,
        due_date=now + timedelta(days=settings.grace_period_days or 7),
        subtotal=subtotal,
        total_tax=total_tax,
        grand_total=grand_total,
        outstanding_amount=grand_total,
        amount_paid=Decimal("0"),
        requires_review=0,
        internal_notes=(
            f"Auto-generated for subscription {sub.subscription_number}. "
            f"Billing period: {period_start.isoformat()} to {period_end_date.isoformat()}"
        ),
        payment_terms=DEFAULT_PAYMENT_TERMS,
        bank_instructions=DEFAULT_BANK_INSTRUCTIONS,
        billing_notes=DEFAULT_BILLING_NOTES,
        **billing,
    )
    db.add(inv)
    db.flush()

    if status == "issued":
        inv.invoice_number = generate_invoice_number(db, company)
        inv.issued_at = now
        inv.share_token = secrets.token_urlsafe(32)

    inv.line_items.append(
        InvoiceLineItem(
            product_id=plan.product_id,
            sort_order=0,
            item_name=plan.name,
            description=plan.description,
            quantity=Decimal(str(qty)),
            unit="Service",
            unit_price=Decimal(str(price)),
            tax_rate=Decimal(str(gst)),
            line_subtotal=subtotal,
            line_total=line_total,
        )
    )

    link = SubscriptionInvoice(
        subscription_id=sub.id,
        invoice_id=inv.id,
        billing_period_start=period_start,
        billing_period_end=period_end_date,
        generated_at=now,
    )
    db.add(link)
    return inv


def advance_billing_period(sub: CustomerSubscription, plan: SubscriptionPlan) -> None:
    period_start = sub.next_billing_date or sub.start_date
    sub.current_period_start = period_start
    sub.current_period_end = period_end(period_start, plan.billing_interval, plan.interval_days)
    sub.next_billing_date = add_interval(period_start, plan.billing_interval, plan.interval_days)


def initialize_subscription_dates(
    sub: CustomerSubscription,
    plan: SubscriptionPlan,
    start: date,
) -> None:
    sub.start_date = start
    if plan.trial_days and plan.trial_days > 0:
        sub.trial_end_date = start + timedelta(days=plan.trial_days)
        sub.status = "trialing"
        sub.current_period_start = start
        sub.current_period_end = sub.trial_end_date
        sub.next_billing_date = sub.trial_end_date + timedelta(days=1)
    else:
        sub.status = "active"
        sub.trial_end_date = None
        sub.current_period_start = start
        sub.current_period_end = period_end(start, plan.billing_interval, plan.interval_days)
        sub.next_billing_date = add_interval(start, plan.billing_interval, plan.interval_days)


def _already_invoiced(db: Session, sub_id: int, period_start: date, period_end_date: date) -> bool:
    return (
        db.query(SubscriptionInvoice.id)
        .filter(
            SubscriptionInvoice.subscription_id == sub_id,
            SubscriptionInvoice.billing_period_start == period_start,
            SubscriptionInvoice.billing_period_end == period_end_date,
        )
        .first()
        is not None
    )


def should_bill_subscription(sub: CustomerSubscription, today: date) -> bool:
    if sub.status == "cancelled" or sub.status == "expired":
        return False
    if sub.status == "trialing":
        if not sub.trial_end_date or sub.trial_end_date >= today:
            return False
    if not sub.next_billing_date or sub.next_billing_date > today:
        return False
    if sub.cancel_at_period_end and sub.current_period_end and sub.current_period_end < today:
        return False
    return True


def expire_cancelled_subscriptions(db: Session, company_id: int, today: date) -> int:
    subs = (
        db.query(CustomerSubscription)
        .filter(
            CustomerSubscription.company_id == company_id,
            CustomerSubscription.cancel_at_period_end.is_(True),
            CustomerSubscription.status.in_(("active", "past_due", "trialing")),
            CustomerSubscription.current_period_end < today,
        )
        .all()
    )
    count = 0
    for sub in subs:
        sub.status = "expired"
        sub.ended_at = _utcnow()
        count += 1
    return count


def sync_past_due_status(db: Session, company_id: int, settings: SubscriptionSettings) -> int:
    grace = settings.grace_period_days or 7
    today = date.today()
    updated = 0
    subs = (
        db.query(CustomerSubscription)
        .options(joinedload(CustomerSubscription.subscription_invoices).joinedload(SubscriptionInvoice.invoice))
        .filter(
            CustomerSubscription.company_id == company_id,
            CustomerSubscription.status.in_(("active", "past_due")),
        )
        .all()
    )
    for sub in subs:
        latest_link = None
        for link in sub.subscription_invoices or []:
            if latest_link is None or link.generated_at > latest_link.generated_at:
                latest_link = link
        if not latest_link or not latest_link.invoice:
            continue
        inv = latest_link.invoice
        if inv.status in ("paid", "cancelled", "written_off", "closed"):
            if sub.status == "past_due":
                sub.status = "active"
                updated += 1
            continue
        due = inv.due_date.date() if inv.due_date else today
        if _float(inv.outstanding_amount) > 0 and today > due + timedelta(days=grace):
            if sub.status != "past_due":
                sub.status = "past_due"
                updated += 1
        elif sub.status == "past_due" and _float(inv.outstanding_amount) <= 0:
            sub.status = "active"
            updated += 1
    return updated


def send_renewal_reminders(db: Session, company: Company, settings: SubscriptionSettings) -> int:
    if not settings.is_enabled:
        return 0
    today = date.today()
    reminder_days = settings.default_reminder_days or [7, 3, 1]
    roles = settings.notify_roles_json or []
    sent = 0

    subs = (
        db.query(CustomerSubscription)
        .options(joinedload(CustomerSubscription.contact), joinedload(CustomerSubscription.plan))
        .filter(
            CustomerSubscription.company_id == company.id,
            CustomerSubscription.status.in_(BILLABLE_STATUSES),
            CustomerSubscription.next_billing_date.isnot(None),
        )
        .all()
    )

    for sub in subs:
        if not sub.next_billing_date:
            continue
        days_until = (sub.next_billing_date - today).days
        contact_name = sub.contact.name if sub.contact else "Customer"
        plan_name = sub.plan.name if sub.plan else "plan"
        link = f"/subscriptions/{sub.id}"

        if days_until == 0:
            title = f"Subscription renewal today — {sub.subscription_number}"
            message = f"{contact_name} ({plan_name}) bills today."
            for role in roles:
                notify_role(
                    db,
                    company_id=company.id,
                    role=role,
                    category="subscription_renewal",
                    title=title,
                    message=message,
                    link_path=link,
                    dedupe_per_day=True,
                )
            sent += 1
        elif days_until in reminder_days:
            title = f"Subscription renewal in {days_until}d — {sub.subscription_number}"
            message = f"{contact_name} ({plan_name}) renews on {sub.next_billing_date.isoformat()}."
            for role in roles:
                notify_role(
                    db,
                    company_id=company.id,
                    role=role,
                    category="subscription_renewal",
                    title=title,
                    message=message,
                    link_path=link,
                    dedupe_per_day=True,
                )
            sent += 1

        if sub.cancel_at_period_end and sub.current_period_end:
            end_days = (sub.current_period_end - today).days
            if 0 <= end_days <= 7:
                title = f"Subscription ending soon — {sub.subscription_number}"
                message = f"{contact_name} cancels at period end ({sub.current_period_end.isoformat()})."
                for role in roles:
                    notify_role(
                        db,
                        company_id=company.id,
                        role=role,
                        category="subscription_cancel",
                        title=title,
                        message=message,
                        link_path=link,
                        dedupe_per_day=True,
                    )
                sent += 1

    return sent


def run_billing(
    db: Session,
    company: Company,
    user: User,
    settings: SubscriptionSettings,
) -> dict:
    today = date.today()
    expire_cancelled_subscriptions(db, company.id, today)
    sync_past_due_status(db, company.id, settings)

    processed = 0
    invoices_created = 0
    skipped = 0
    invoice_ids: list[int] = []

    subs = (
        db.query(CustomerSubscription)
        .options(joinedload(CustomerSubscription.plan), joinedload(CustomerSubscription.contact))
        .filter(
            CustomerSubscription.company_id == company.id,
            CustomerSubscription.status.in_(BILLABLE_STATUSES),
        )
        .all()
    )

    for sub in subs:
        if not should_bill_subscription(sub, today):
            continue
        plan = sub.plan
        if not plan:
            skipped += 1
            continue

        if sub.status == "trialing" and sub.trial_end_date and sub.trial_end_date < today:
            sub.status = "active"

        period_start = sub.next_billing_date or today
        period_end_date = period_end(period_start, plan.billing_interval, plan.interval_days)

        if _already_invoiced(db, sub.id, period_start, period_end_date):
            skipped += 1
            advance_billing_period(sub, plan)
            continue

        processed += 1
        inv = create_subscription_invoice(
            db, company, user, sub, plan, settings, period_start, period_end_date
        )
        invoice_ids.append(inv.id)
        invoices_created += 1
        advance_billing_period(sub, plan)

    return {
        "processed": processed,
        "invoices_created": invoices_created,
        "skipped": skipped,
        "invoice_ids": invoice_ids,
    }


def classify_plan_change(from_plan: SubscriptionPlan, to_plan: SubscriptionPlan) -> str:
    from_price = _float(from_plan.price)
    to_price = _float(to_plan.price)
    if to_price > from_price:
        return "upgrade"
    if to_price < from_price:
        return "downgrade"
    return "same_tier"


def change_subscription_plan(
    db: Session,
    sub: CustomerSubscription,
    from_plan: SubscriptionPlan,
    to_plan: SubscriptionPlan,
    effective_date: date,
    user: User,
    notes: str | None = None,
) -> SubscriptionPlanChange:
    change_type = classify_plan_change(from_plan, to_plan)
    if change_type not in CHANGE_TYPES:
        change_type = "same_tier"

    row = SubscriptionPlanChange(
        subscription_id=sub.id,
        from_plan_id=from_plan.id,
        to_plan_id=to_plan.id,
        effective_date=effective_date,
        change_type=change_type,
        notes=notes,
        created_by_id=user.id,
    )
    db.add(row)

    sub.plan_id = to_plan.id
    if effective_date <= date.today():
        if from_plan.billing_interval != to_plan.billing_interval:
            anchor = sub.next_billing_date or effective_date
            sub.next_billing_date = add_interval(anchor, to_plan.billing_interval, to_plan.interval_days)
            sub.current_period_end = period_end(
                sub.current_period_start or effective_date,
                to_plan.billing_interval,
                to_plan.interval_days,
            )
    return row


def validate_plan_payload(interval: str, interval_days: int | None, status: str | None = None) -> None:
    if interval not in BILLING_INTERVALS:
        raise ValueError(f"Invalid billing interval: {interval}")
    if interval == "custom_days" and (not interval_days or interval_days < 1):
        raise ValueError("interval_days required for custom_days billing")
    if status and status not in PLAN_STATUSES:
        raise ValueError(f"Invalid plan status: {status}")
