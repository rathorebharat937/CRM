"""Subscription Management API."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from auth_utils import get_client_ip, get_db, require_permission
from models import (
    Company,
    Contact,
    CustomerSubscription,
    SubscriptionInvoice,
    SubscriptionPlan,
    SubscriptionPlanChange,
    SubscriptionSettings,
    User,
)
from services.subscription_service import (
    change_subscription_plan,
    generate_subscription_number,
    initialize_subscription_dates,
    mrr_for_subscription,
    run_billing,
    send_renewal_reminders,
    sync_past_due_status,
    validate_plan_payload,
)
from subscriptions_config import (
    DEFAULT_AUTO_INVOICE_MODE,
    DEFAULT_GRACE_PERIOD_DAYS,
    DEFAULT_NOTIFY_ROLES,
    DEFAULT_SLA_REMINDER_DAYS,
    DEFAULT_SUBSCRIPTION_PREFIX,
    PLAN_STATUSES,
)
from subscriptions_schemas import (
    BillingRunResult,
    PlanCreateRequest,
    PlanResponse,
    PlanUpdateRequest,
    SubscriptionCancelRequest,
    SubscriptionChangePlanRequest,
    SubscriptionCreateRequest,
    SubscriptionInvoiceLink,
    SubscriptionListItem,
    SubscriptionListResponse,
    SubscriptionResponse,
    SubscriptionSettingsResponse,
    SubscriptionSettingsUpdateRequest,
    SubscriptionsDashboardResponse,
    PlanChangeItem,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)


def _get_company(db: Session) -> Company:
    company = db.query(Company).first()
    if not company:
        raise HTTPException(status_code=400, detail="Company must be configured")
    return company


def _get_settings(db: Session, company: Company) -> SubscriptionSettings:
    settings = (
        db.query(SubscriptionSettings).filter(SubscriptionSettings.company_id == company.id).first()
    )
    if settings:
        return settings
    settings = SubscriptionSettings(
        company_id=company.id,
        is_enabled=True,
        default_reminder_days=DEFAULT_SLA_REMINDER_DAYS,
        notify_roles_json=DEFAULT_NOTIFY_ROLES,
        subscription_prefix=DEFAULT_SUBSCRIPTION_PREFIX,
        auto_invoice_mode=DEFAULT_AUTO_INVOICE_MODE,
        grace_period_days=DEFAULT_GRACE_PERIOD_DAYS,
    )
    db.add(settings)
    db.flush()
    return settings


def _require_enabled(settings: SubscriptionSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="Subscriptions module is not enabled")


def _settings_response(settings: SubscriptionSettings) -> SubscriptionSettingsResponse:
    return SubscriptionSettingsResponse(
        is_enabled=settings.is_enabled,
        subscription_prefix=settings.subscription_prefix or DEFAULT_SUBSCRIPTION_PREFIX,
        default_reminder_days=settings.default_reminder_days or DEFAULT_SLA_REMINDER_DAYS,
        auto_invoice_mode=settings.auto_invoice_mode or DEFAULT_AUTO_INVOICE_MODE,
        auto_invoice_on_billing_date=bool(settings.auto_invoice_on_billing_date),
        grace_period_days=int(settings.grace_period_days or DEFAULT_GRACE_PERIOD_DAYS),
        notify_roles_json=settings.notify_roles_json or [],
        allow_immediate_cancel=bool(settings.allow_immediate_cancel),
    )


def _plan_response(plan: SubscriptionPlan) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        plan_code=plan.plan_code,
        name=plan.name,
        description=plan.description,
        billing_interval=plan.billing_interval,
        interval_days=plan.interval_days,
        price=_float(plan.price),
        currency=plan.currency or "INR",
        gst_rate=_float(plan.gst_rate),
        product_id=plan.product_id,
        trial_days=int(plan.trial_days or 0),
        status=plan.status,
        sort_order=int(plan.sort_order or 0),
    )


def _sub_list_item(sub: CustomerSubscription) -> SubscriptionListItem:
    return SubscriptionListItem(
        id=sub.id,
        subscription_number=sub.subscription_number,
        contact_id=sub.contact_id,
        contact_name=sub.contact.name if sub.contact else None,
        plan_id=sub.plan_id,
        plan_name=sub.plan.name if sub.plan else None,
        status=sub.status,
        quantity=int(sub.quantity or 1),
        unit_price=_float(sub.unit_price) if sub.unit_price is not None else None,
        start_date=sub.start_date,
        next_billing_date=sub.next_billing_date,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=bool(sub.cancel_at_period_end),
        mrr_contribution=mrr_for_subscription(sub),
    )


def _sub_response(sub: CustomerSubscription) -> SubscriptionResponse:
    invoices = []
    for link in sorted(sub.subscription_invoices or [], key=lambda x: x.generated_at or _utcnow(), reverse=True):
        inv = link.invoice
        invoices.append(
            SubscriptionInvoiceLink(
                id=link.id,
                invoice_id=link.invoice_id,
                invoice_number=inv.invoice_number if inv else None,
                invoice_status=inv.status if inv else None,
                grand_total=_float(inv.grand_total) if inv else None,
                billing_period_start=link.billing_period_start,
                billing_period_end=link.billing_period_end,
                generated_at=link.generated_at,
            )
        )
    changes = []
    for row in sorted(sub.plan_changes or [], key=lambda x: x.created_at or _utcnow(), reverse=True):
        changes.append(
            PlanChangeItem(
                id=row.id,
                from_plan_name=row.from_plan.name if row.from_plan else None,
                to_plan_name=row.to_plan.name if row.to_plan else None,
                effective_date=row.effective_date,
                change_type=row.change_type,
                notes=row.notes,
                created_at=row.created_at,
            )
        )
    return SubscriptionResponse(
        id=sub.id,
        subscription_number=sub.subscription_number,
        contact_id=sub.contact_id,
        contact_name=sub.contact.name if sub.contact else None,
        plan_id=sub.plan_id,
        plan_name=sub.plan.name if sub.plan else None,
        status=sub.status,
        quantity=int(sub.quantity or 1),
        unit_price=_float(sub.unit_price) if sub.unit_price is not None else None,
        start_date=sub.start_date,
        trial_end_date=sub.trial_end_date,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        next_billing_date=sub.next_billing_date,
        cancel_at_period_end=bool(sub.cancel_at_period_end),
        cancelled_at=sub.cancelled_at,
        cancellation_reason=sub.cancellation_reason,
        ended_at=sub.ended_at,
        notes=sub.notes,
        mrr_contribution=mrr_for_subscription(sub),
        invoices=invoices,
        plan_changes=changes,
    )


def _load_subscription(db: Session, company_id: int, sub_id: int) -> CustomerSubscription:
    sub = (
        db.query(CustomerSubscription)
        .options(
            joinedload(CustomerSubscription.contact),
            joinedload(CustomerSubscription.plan),
            joinedload(CustomerSubscription.subscription_invoices).joinedload(SubscriptionInvoice.invoice),
            joinedload(CustomerSubscription.plan_changes).joinedload(SubscriptionPlanChange.from_plan),
            joinedload(CustomerSubscription.plan_changes).joinedload(SubscriptionPlanChange.to_plan),
        )
        .filter(CustomerSubscription.id == sub_id, CustomerSubscription.company_id == company_id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.get("/settings", response_model=SubscriptionSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("subscriptions.view")),
):
    company = _get_company(db)
    return _settings_response(_get_settings(db, company))


@router.put("/settings", response_model=SubscriptionSettingsResponse)
def update_settings(
    payload: SubscriptionSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("subscriptions.manage_settings")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    data = payload.model_dump(exclude_unset=True)
    if "auto_invoice_mode" in data and data["auto_invoice_mode"] not in ("draft", "issue"):
        raise HTTPException(status_code=400, detail="auto_invoice_mode must be draft or issue")
    for key, value in data.items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    log_activity(
        db,
        "subscription_settings_updated",
        user_id=user.id,
        details={"company_id": company.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _settings_response(settings)


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("subscriptions.view")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))
    q = db.query(SubscriptionPlan).filter(SubscriptionPlan.company_id == company.id)
    if status:
        q = q.filter(SubscriptionPlan.status == status)
    plans = q.order_by(SubscriptionPlan.sort_order, SubscriptionPlan.name).all()
    return [_plan_response(p) for p in plans]


@router.post("/plans", response_model=PlanResponse)
def create_plan(
    payload: PlanCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("subscriptions.manage_plans")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))
    try:
        validate_plan_payload(payload.billing_interval, payload.interval_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    exists = (
        db.query(SubscriptionPlan.id)
        .filter(SubscriptionPlan.company_id == company.id, SubscriptionPlan.plan_code == payload.plan_code)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Plan code already exists")

    plan = SubscriptionPlan(
        company_id=company.id,
        plan_code=payload.plan_code,
        name=payload.name,
        description=payload.description,
        billing_interval=payload.billing_interval,
        interval_days=payload.interval_days,
        price=payload.price,
        currency=payload.currency,
        gst_rate=payload.gst_rate,
        product_id=payload.product_id,
        trial_days=payload.trial_days,
        sort_order=payload.sort_order,
        status="active",
    )
    db.add(plan)
    db.flush()
    log_activity(
        db,
        "subscription_plan_created",
        user_id=user.id,
        details={"plan_id": plan.id, "plan_code": plan.plan_code},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(plan)
    return _plan_response(plan)


@router.get("/plans/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("subscriptions.view")),
):
    company = _get_company(db)
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.id == plan_id, SubscriptionPlan.company_id == company.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_response(plan)


@router.put("/plans/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: int,
    payload: PlanUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("subscriptions.manage_plans")),
):
    company = _get_company(db)
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.id == plan_id, SubscriptionPlan.company_id == company.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    data = payload.model_dump(exclude_unset=True)
    interval = data.get("billing_interval", plan.billing_interval)
    interval_days = data.get("interval_days", plan.interval_days)
    status = data.get("status")
    try:
        validate_plan_payload(interval, interval_days, status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for key, value in data.items():
        setattr(plan, key, value)
    log_activity(
        db,
        "subscription_plan_updated",
        user_id=user.id,
        details={"plan_id": plan.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(plan)
    return _plan_response(plan)


@router.get("/dashboard", response_model=SubscriptionsDashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("subscriptions.view")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)

    today = date.today()
    sync_past_due_status(db, company.id, settings)
    send_renewal_reminders(db, company, settings)
    db.commit()

    base = (
        db.query(CustomerSubscription)
        .options(joinedload(CustomerSubscription.contact), joinedload(CustomerSubscription.plan))
        .filter(CustomerSubscription.company_id == company.id)
    )
    all_subs = base.all()

    active_subs = [s for s in all_subs if s.status in ("active", "trialing", "past_due")]
    mrr = sum(mrr_for_subscription(s) for s in active_subs)

    renewals_7d = [s for s in active_subs if s.next_billing_date and 0 <= (s.next_billing_date - today).days <= 7]
    renewals_30d = [s for s in active_subs if s.next_billing_date and 0 <= (s.next_billing_date - today).days <= 30]
    past_due = [s for s in all_subs if s.status == "past_due"]

    month_start = today.replace(day=1)
    cancelled_mtd = [
        s
        for s in all_subs
        if s.status in ("cancelled", "expired")
        and s.cancelled_at
        and s.cancelled_at.date() >= month_start
    ]
    new_mtd = [s for s in all_subs if s.created_at and s.created_at.date() >= month_start]

    renewals_due = sorted(
        renewals_7d,
        key=lambda s: s.next_billing_date or today,
    )[:20]
    recently_cancelled = sorted(
        [s for s in all_subs if s.status in ("cancelled", "expired")],
        key=lambda s: s.cancelled_at or s.ended_at or _utcnow(),
        reverse=True,
    )[:10]

    return SubscriptionsDashboardResponse(
        active_subscriptions=len(active_subs),
        mrr=round(mrr, 2),
        renewals_due_7d=len(renewals_7d),
        renewals_due_30d=len(renewals_30d),
        past_due_count=len(past_due),
        cancelled_mtd=len(cancelled_mtd),
        new_mtd=len(new_mtd),
        renewals_due=[_sub_list_item(s) for s in renewals_due],
        past_due=[_sub_list_item(s) for s in past_due[:20]],
        recently_cancelled=[_sub_list_item(s) for s in recently_cancelled],
    )


@router.get("", response_model=SubscriptionListResponse)
def list_subscriptions(
    status: str | None = Query(None),
    plan_id: int | None = Query(None),
    contact_id: int | None = Query(None),
    renewal_from: date | None = Query(None),
    renewal_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("subscriptions.view")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))

    q = (
        db.query(CustomerSubscription)
        .options(joinedload(CustomerSubscription.contact), joinedload(CustomerSubscription.plan))
        .filter(CustomerSubscription.company_id == company.id)
    )
    if status:
        q = q.filter(CustomerSubscription.status == status)
    if plan_id:
        q = q.filter(CustomerSubscription.plan_id == plan_id)
    if contact_id:
        q = q.filter(CustomerSubscription.contact_id == contact_id)
    if renewal_from:
        q = q.filter(CustomerSubscription.next_billing_date >= renewal_from)
    if renewal_to:
        q = q.filter(CustomerSubscription.next_billing_date <= renewal_to)

    total = q.count()
    subs = q.order_by(CustomerSubscription.created_at.desc()).offset(skip).limit(limit).all()
    return SubscriptionListResponse(items=[_sub_list_item(s) for s in subs], total=total)


@router.post("", response_model=SubscriptionResponse)
def create_subscription(
    payload: SubscriptionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("subscriptions.create")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    contact = (
        db.query(Contact)
        .filter(Contact.id == payload.contact_id, Contact.company_id == company.id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.id == payload.plan_id, SubscriptionPlan.company_id == company.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status == "archived":
        raise HTTPException(status_code=400, detail="Cannot subscribe to archived plan")

    start = payload.start_date or date.today()
    prefix = settings.subscription_prefix or DEFAULT_SUBSCRIPTION_PREFIX
    sub = CustomerSubscription(
        company_id=company.id,
        subscription_number=generate_subscription_number(db, company.id, prefix),
        contact_id=contact.id,
        plan_id=plan.id,
        quantity=max(1, payload.quantity),
        unit_price=payload.unit_price,
        notes=payload.notes,
        created_by_id=user.id,
    )
    initialize_subscription_dates(sub, plan, start)
    if sub.next_billing_date and sub.next_billing_date < sub.start_date:
        raise HTTPException(status_code=400, detail="next_billing_date must be >= start_date")

    db.add(sub)
    db.flush()
    log_activity(
        db,
        "subscription_created",
        user_id=user.id,
        details={"subscription_id": sub.id, "subscription_number": sub.subscription_number},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _sub_response(_load_subscription(db, company.id, sub.id))


@router.get("/{sub_id}", response_model=SubscriptionResponse)
def get_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("subscriptions.view")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))
    return _sub_response(_load_subscription(db, company.id, sub_id))


@router.post("/{sub_id}/cancel", response_model=SubscriptionResponse)
def cancel_subscription(
    sub_id: int,
    payload: SubscriptionCancelRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("subscriptions.cancel")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    sub = _load_subscription(db, company.id, sub_id)
    if sub.status == "expired":
        raise HTTPException(status_code=400, detail="Subscription already expired")

    sub.cancellation_reason = payload.cancellation_reason
    sub.cancelled_at = _utcnow()

    if payload.immediate:
        if not settings.allow_immediate_cancel:
            raise HTTPException(status_code=400, detail="Immediate cancel is disabled in settings")
        sub.status = "cancelled"
        sub.cancel_at_period_end = False
        sub.ended_at = _utcnow()
        sub.next_billing_date = None
    else:
        sub.cancel_at_period_end = True

    log_activity(
        db,
        "subscription_cancelled",
        user_id=user.id,
        details={"subscription_id": sub.id, "immediate": payload.immediate},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _sub_response(_load_subscription(db, company.id, sub_id))


@router.post("/{sub_id}/change-plan", response_model=SubscriptionResponse)
def change_plan(
    sub_id: int,
    payload: SubscriptionChangePlanRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("subscriptions.change_plan")),
):
    company = _get_company(db)
    _require_enabled(_get_settings(db, company))

    sub = _load_subscription(db, company.id, sub_id)
    if sub.status in ("cancelled", "expired"):
        raise HTTPException(status_code=400, detail="Cannot change plan on ended subscription")

    to_plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.id == payload.new_plan_id, SubscriptionPlan.company_id == company.id)
        .first()
    )
    if not to_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if to_plan.status == "archived":
        raise HTTPException(status_code=400, detail="Cannot change to archived plan")

    from_plan = sub.plan
    if not from_plan:
        raise HTTPException(status_code=400, detail="Current plan missing")

    effective = payload.effective_date or date.today()
    change_subscription_plan(db, sub, from_plan, to_plan, effective, user, payload.notes)
    log_activity(
        db,
        "subscription_plan_changed",
        user_id=user.id,
        details={"subscription_id": sub.id, "to_plan_id": to_plan.id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _sub_response(_load_subscription(db, company.id, sub_id))


@router.post("/run-billing", response_model=BillingRunResult)
def run_billing_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("subscriptions.bill")),
):
    company = _get_company(db)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    result = run_billing(db, company, user, settings)
    log_activity(
        db,
        "subscription_invoice_generated",
        user_id=user.id,
        details=result,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return BillingRunResult(**result)


@router.get("/{sub_id}/invoices", response_model=list[SubscriptionInvoiceLink])
def list_subscription_invoices(
    sub_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("subscriptions.view")),
):
    company = _get_company(db)
    sub = _load_subscription(db, company.id, sub_id)
    return _sub_response(sub).invoices
