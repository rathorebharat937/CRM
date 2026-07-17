from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from tenant_utils import get_current_company
from auth_utils import get_db, require_permission
from config import STAFF_ROLES
from deal_config import DEAL_STAGE_LABELS, PIPELINE_STAGES
from models import Company, Contact, Deal, Invoice, Lead, Quotation, SalesOrder, User
from permissions import role_has_permission
from sales_report_config import PERIOD_LABELS, REPORT_PERIODS, STALE_DEAL_DAYS
from schemas import (
    SalesReportConversionResponse,
    SalesReportExecutiveResponse,
    SalesReportKpiCard,
    SalesReportLeadSourceResponse,
    SalesReportOverviewResponse,
    SalesReportPendingDeal,
    SalesReportPendingDealsResponse,
    SalesReportPeriodOption,
    SalesReportPipelineHealthResponse,
    SalesReportPipelineStage,
    SalesReportRankRow,
    SalesReportRevenueResponse,
    SalesReportTrendPoint,
    SalesReportConversionFunnel,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/sales-reports", tags=["sales-reports"])




def _float(v) -> float:
    return 0.0 if v is None else float(v)


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _can_view_company(user: User, db: Session) -> bool:
    return role_has_permission(db, user.role, "reports.view_company")


def _can_view_team(user: User, db: Session) -> bool:
    return _can_view_company(user, db) or role_has_permission(db, user.role, "reports.view_team")


def _can_view_financial(user: User, db: Session) -> bool:
    return role_has_permission(db, user.role, "reports.view_financial")


def _resolve_owner_filter(user: User, db: Session, owner_id: int | None) -> int | None:
    if owner_id:
        if not _can_view_team(user, db) and owner_id != user.id:
            raise HTTPException(status_code=403, detail="Cannot view another owner's reports")
        return owner_id
    if _can_view_team(user, db):
        return None
    return user.id


def _period_bounds(period: str, date_from: datetime | None, date_to: datetime | None):
    now = datetime.now(timezone.utc)
    if period == "custom":
        if not date_from or not date_to:
            raise HTTPException(status_code=400, detail="Custom period requires date_from and date_to")
        start = date_from if date_from.tzinfo else date_from.replace(tzinfo=timezone.utc)
        end = date_to if date_to.tzinfo else date_to.replace(tzinfo=timezone.utc)
    elif period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "week":
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "quarter":
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    else:
        raise HTTPException(status_code=400, detail=f"Period must be one of: {', '.join(REPORT_PERIODS)}")

    duration = end - start
    prev_end = start
    prev_start = start - duration
    return start, end, prev_start, prev_end, PERIOD_LABELS.get(period, period)


def _in_period(column, start, end):
    return column >= start, column <= end


def _deal_owner_filter(query, owner_id: int | None):
    if owner_id:
        return query.filter(Deal.assigned_to_id == owner_id)
    return query


def _lead_owner_filter(query, owner_id: int | None):
    if owner_id:
        return query.filter(Lead.assigned_to_id == owner_id)
    return query


def _pending_deal_row(deal: Deal) -> SalesReportPendingDeal:
    now = datetime.now(timezone.utc)
    updated = deal.updated_at or deal.created_at
    days_stale = (now - updated).days if updated else 0
    is_stale = days_stale >= STALE_DEAL_DAYS
    is_overdue = bool(deal.expected_close_date and deal.expected_close_date < now)
    badge = None
    if is_overdue:
        badge = "Overdue"
    elif is_stale:
        badge = "Stale"
    elif _float(deal.expected_value) >= 500000:
        badge = "High Value"
    return SalesReportPendingDeal(
        id=deal.id,
        title=deal.title,
        stage=deal.stage,
        stage_label=DEAL_STAGE_LABELS.get(deal.stage, deal.stage),
        expected_value=_float(deal.expected_value),
        currency=deal.currency,
        owner_name=deal.assigned_to.name if deal.assigned_to else None,
        expected_close_date=deal.expected_close_date,
        updated_at=deal.updated_at,
        days_stale=days_stale,
        is_overdue=is_overdue,
        is_stale=is_stale,
        badge=badge,
    )


@router.get("/periods", response_model=list[SalesReportPeriodOption])
def periods(_: User = Depends(require_permission("reports.view"))):
    return [SalesReportPeriodOption(value=p, label=PERIOD_LABELS[p]) for p in REPORT_PERIODS]


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def assignees(user: User = Depends(require_permission("reports.view")), db: Session = Depends(get_db)):
    if not _can_view_team(user, db):
        return [StaffAssigneeResponse(id=user.id, name=user.name, email=user.email, role=user.role)]
    users = db.query(User).filter(User.role.in_(STAFF_ROLES), User.status == "active").order_by(User.name).all()
    return [StaffAssigneeResponse(id=u.id, name=u.name, email=u.email, role=u.role) for u in users]


@router.get("/overview", response_model=SalesReportOverviewResponse)
def overview(
    period: str = Query("month"),
    owner_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user: User = Depends(require_permission("reports.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    owner_id = _resolve_owner_filter(user, db, owner_id)
    start, end, prev_start, prev_end, period_label = _period_bounds(period, date_from, date_to)

    leads_q = db.query(Lead).filter(Lead.company_id == company.id, Lead.created_at >= start, Lead.created_at <= end)
    leads_q = _lead_owner_filter(leads_q, owner_id)
    total_leads = leads_q.count()

    deals_q = db.query(Deal).filter(Deal.company_id == company.id, Deal.created_at >= start, Deal.created_at <= end)
    deals_q = _deal_owner_filter(deals_q, owner_id)
    total_deals = deals_q.count()

    won_q = db.query(Deal).filter(
        Deal.company_id == company.id,
        Deal.stage == "won",
        Deal.closed_at >= start,
        Deal.closed_at <= end,
    )
    won_q = _deal_owner_filter(won_q, owner_id)
    won_deals = won_q.all()
    won_count = len(won_deals)
    won_revenue = sum(_float(d.expected_value) for d in won_deals)

    prev_won_q = db.query(Deal).filter(
        Deal.company_id == company.id,
        Deal.stage == "won",
        Deal.closed_at >= prev_start,
        Deal.closed_at < prev_end,
    )
    prev_won_q = _deal_owner_filter(prev_won_q, owner_id)
    prev_won_revenue = sum(_float(d.expected_value) for d in prev_won_q.all())

    open_q = db.query(Deal).filter(Deal.company_id == company.id, Deal.stage.in_(PIPELINE_STAGES))
    open_q = _deal_owner_filter(open_q, owner_id)
    open_deals = open_q.all()
    pending_value = sum(_float(d.expected_value) for d in open_deals)

    lead_to_deal = _rate(total_deals, total_leads)
    deal_to_win = _rate(won_count, total_deals)
    avg_deal = won_revenue / won_count if won_count else 0
    revenue_delta = None
    if prev_won_revenue > 0:
        revenue_delta = round(((won_revenue - prev_won_revenue) / prev_won_revenue) * 100, 1)

    stale_count = sum(1 for d in open_deals if (datetime.now(timezone.utc) - (d.updated_at or d.created_at)).days >= STALE_DEAL_DAYS)

    kpis = [
        SalesReportKpiCard(key="conversion", label="Lead→Deal conversion", value=lead_to_deal, unit="%"),
        SalesReportKpiCard(key="win_rate", label="Deal win rate", value=deal_to_win, unit="%"),
        SalesReportKpiCard(
            key="revenue",
            label="Revenue (won deals)",
            value=won_revenue,
            unit="INR",
            delta_percent=revenue_delta,
            delta_label="vs previous period",
        ),
        SalesReportKpiCard(key="pending_value", label="Pending pipeline", value=pending_value, unit="INR"),
        SalesReportKpiCard(key="avg_deal", label="Avg deal size", value=round(avg_deal, 0), unit="INR"),
        SalesReportKpiCard(key="won_count", label="Closed won", value=won_count),
        SalesReportKpiCard(key="stale", label="Stale deals", value=stale_count),
    ]

    if not _can_view_financial(user, db):
        kpis = [k for k in kpis if k.key not in ("revenue", "pending_value", "avg_deal")]

    # Monthly trend (last 6 months won revenue)
    trend = []
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 28)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)
        m_q = db.query(Deal).filter(
            Deal.company_id == company.id,
            Deal.stage == "won",
            Deal.closed_at >= month_start,
            Deal.closed_at < month_end,
        )
        m_q = _deal_owner_filter(m_q, owner_id)
        val = sum(_float(d.expected_value) for d in m_q.all())
        trend.append(SalesReportTrendPoint(label=month_start.strftime("%b %Y"), value=val))

    # Top sources
    source_rows = (
        db.query(Lead.source, func.count(Lead.id))
        .filter(Lead.company_id == company.id, Lead.created_at >= start, Lead.created_at <= end)
        .group_by(Lead.source)
        .order_by(func.count(Lead.id).desc())
        .limit(5)
        .all()
    )
    top_sources = [SalesReportRankRow(name=s or "Unknown", count=c) for s, c in source_rows]

    # Top performers by won revenue
    perf_rows = (
        db.query(User.name, func.count(Deal.id), func.coalesce(func.sum(Deal.expected_value), 0))
        .join(Deal, Deal.assigned_to_id == User.id)
        .filter(
            Deal.company_id == company.id,
            Deal.stage == "won",
            Deal.closed_at >= start,
            Deal.closed_at <= end,
        )
        .group_by(User.name)
        .order_by(func.coalesce(func.sum(Deal.expected_value), 0).desc())
        .limit(5)
        .all()
    )
    top_performers = [
        SalesReportRankRow(name=n, count=c, value=_float(v), badge="High Performer" if _float(v) > 0 else None)
        for n, c, v in perf_rows
    ]

    pending_sorted = sorted(open_deals, key=lambda d: _float(d.expected_value), reverse=True)[:5]
    top_pending = [_pending_deal_row(d) for d in pending_sorted]

    return SalesReportOverviewResponse(
        period_label=period_label,
        date_from=start,
        date_to=end,
        kpis=kpis,
        revenue_trend=trend if _can_view_financial(user, db) else [],
        top_sources=top_sources,
        top_performers=top_performers,
        top_pending_deals=top_pending,
    )


@router.get("/conversion", response_model=SalesReportConversionResponse)
def conversion_report(
    period: str = Query("month"),
    owner_id: int | None = None,
    user: User = Depends(require_permission("reports.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    owner_id = _resolve_owner_filter(user, db, owner_id)
    start, end, prev_start, prev_end, period_label = _period_bounds(period, None, None)

    leads = _lead_owner_filter(
        db.query(Lead).filter(Lead.company_id == company.id, Lead.created_at >= start, Lead.created_at <= end),
        owner_id,
    ).count()

    deals = _deal_owner_filter(
        db.query(Deal).filter(Deal.company_id == company.id, Deal.created_at >= start, Deal.created_at <= end),
        owner_id,
    ).count()

    won = _deal_owner_filter(
        db.query(Deal).filter(
            Deal.company_id == company.id,
            Deal.stage == "won",
            Deal.closed_at >= start,
            Deal.closed_at <= end,
        ),
        owner_id,
    ).count()

    quotes = db.query(Quotation).filter(
        Quotation.company_id == company.id,
        Quotation.created_at >= start,
        Quotation.created_at <= end,
    )
    if owner_id:
        quotes = quotes.filter(Quotation.assigned_to_id == owner_id)
    quote_count = quotes.count()

    orders = db.query(SalesOrder).filter(
        SalesOrder.company_id == company.id,
        SalesOrder.created_at >= start,
        SalesOrder.created_at <= end,
    )
    if owner_id:
        orders = orders.filter(SalesOrder.assigned_to_id == owner_id)
    order_count = orders.count()

    invoices = db.query(Invoice).filter(
        Invoice.company_id == company.id,
        Invoice.issued_at >= start,
        Invoice.issued_at <= end,
        Invoice.invoice_number.isnot(None),
    )
    if owner_id:
        invoices = invoices.filter(Invoice.assigned_to_id == owner_id)
    invoice_count = invoices.count()

    prev_leads = _lead_owner_filter(
        db.query(Lead).filter(Lead.company_id == company.id, Lead.created_at >= prev_start, Lead.created_at < prev_end),
        owner_id,
    ).count()
    prev_deals = _deal_owner_filter(
        db.query(Deal).filter(Deal.company_id == company.id, Deal.created_at >= prev_start, Deal.created_at < prev_end),
        owner_id,
    ).count()
    prev_won = _deal_owner_filter(
        db.query(Deal).filter(
            Deal.company_id == company.id,
            Deal.stage == "won",
            Deal.closed_at >= prev_start,
            Deal.closed_at < prev_end,
        ),
        owner_id,
    ).count()

    lead_to_deal = _rate(deals, leads)
    deal_to_win = _rate(won, deals)
    quote_to_order = _rate(order_count, quote_count)
    order_to_invoice = _rate(invoice_count, order_count)

    funnel = [
        SalesReportConversionFunnel(stage="leads", label="Leads", count=leads, value=0),
        SalesReportConversionFunnel(stage="deals", label="Deals", count=deals, value=0, rate_from_previous=lead_to_deal),
        SalesReportConversionFunnel(stage="won", label="Won", count=won, value=0, rate_from_previous=deal_to_win),
        SalesReportConversionFunnel(stage="quotes", label="Quotations", count=quote_count, value=0),
        SalesReportConversionFunnel(stage="orders", label="Orders", count=order_count, value=0, rate_from_previous=quote_to_order),
        SalesReportConversionFunnel(stage="invoices", label="Invoices", count=invoice_count, value=0, rate_from_previous=order_to_invoice),
    ]

    by_source = []
    for source, lead_cnt in (
        db.query(Lead.source, func.count(Lead.id))
        .filter(Lead.company_id == company.id, Lead.created_at >= start, Lead.created_at <= end)
        .group_by(Lead.source)
        .all()
    ):
        deal_cnt = (
            db.query(func.count(Deal.id))
            .join(Lead, Deal.lead_id == Lead.id)
            .filter(Lead.company_id == company.id, Lead.source == source, Deal.created_at >= start, Deal.created_at <= end)
            .scalar()
            or 0
        )
        by_source.append(SalesReportRankRow(name=source or "Unknown", count=lead_cnt, rate=_rate(deal_cnt, lead_cnt)))
    by_source.sort(key=lambda r: r.rate or 0, reverse=True)

    by_owner = []
    for name, lead_cnt in (
        db.query(User.name, func.count(Lead.id))
        .join(Lead, Lead.assigned_to_id == User.id)
        .filter(Lead.company_id == company.id, Lead.created_at >= start, Lead.created_at <= end)
        .group_by(User.name)
        .all()
    ):
        deal_cnt = (
            db.query(func.count(Deal.id))
            .join(User, Deal.assigned_to_id == User.id)
            .filter(Deal.company_id == company.id, User.name == name, Deal.created_at >= start, Deal.created_at <= end)
            .scalar()
            or 0
        )
        by_owner.append(SalesReportRankRow(name=name, count=lead_cnt, rate=_rate(deal_cnt, lead_cnt)))
    by_owner.sort(key=lambda r: r.rate or 0, reverse=True)

    return SalesReportConversionResponse(
        period_label=period_label,
        funnel=funnel,
        lead_to_deal_rate=lead_to_deal,
        deal_to_win_rate=deal_to_win,
        quote_to_order_rate=quote_to_order,
        order_to_invoice_rate=order_to_invoice,
        by_source=by_source,
        by_owner=by_owner,
        previous_lead_to_deal_rate=_rate(prev_deals, prev_leads) if prev_leads else None,
        previous_deal_to_win_rate=_rate(prev_won, prev_deals) if prev_deals else None,
    )


@router.get("/revenue", response_model=SalesReportRevenueResponse)
def revenue_report(
    period: str = Query("month"),
    owner_id: int | None = None,
    user: User = Depends(require_permission("reports.view_financial")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    owner_id = _resolve_owner_filter(user, db, owner_id)
    start, end, prev_start, prev_end, period_label = _period_bounds(period, None, None)

    won_deals = _deal_owner_filter(
        db.query(Deal).filter(
            Deal.company_id == company.id,
            Deal.stage == "won",
            Deal.closed_at >= start,
            Deal.closed_at <= end,
        ),
        owner_id,
    ).all()
    booked = sum(_float(d.expected_value) for d in won_deals)

    prev_booked = sum(
        _float(d.expected_value)
        for d in _deal_owner_filter(
            db.query(Deal).filter(
                Deal.company_id == company.id,
                Deal.stage == "won",
                Deal.closed_at >= prev_start,
                Deal.closed_at < prev_end,
            ),
            owner_id,
        ).all()
    )

    inv_q = db.query(Invoice).filter(Invoice.company_id == company.id)
    if owner_id:
        inv_q = inv_q.filter(Invoice.assigned_to_id == owner_id)
    invoices = inv_q.filter(Invoice.invoice_number.isnot(None)).all()
    collected = sum(_float(i.amount_paid) for i in invoices)
    outstanding = sum(_float(i.outstanding_amount) for i in invoices)

    pipeline = sum(
        _float(d.expected_value)
        for d in _deal_owner_filter(
            db.query(Deal).filter(Deal.company_id == company.id, Deal.stage.in_(PIPELINE_STAGES)),
            owner_id,
        ).all()
    )

    won_count = len(won_deals)
    avg_deal = booked / won_count if won_count else 0

    trend = []
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 28)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = month_start.replace(month=month_start.month % 12 + 1) if month_start.month < 12 else month_start.replace(year=month_start.year + 1, month=1)
        val = sum(
            _float(d.expected_value)
            for d in _deal_owner_filter(
                db.query(Deal).filter(
                    Deal.company_id == company.id,
                    Deal.stage == "won",
                    Deal.closed_at >= month_start,
                    Deal.closed_at < month_end,
                ),
                owner_id,
            ).all()
        )
        trend.append(SalesReportTrendPoint(label=month_start.strftime("%b %Y"), value=val))

    by_owner = []
    for name, cnt, val in (
        db.query(User.name, func.count(Deal.id), func.coalesce(func.sum(Deal.expected_value), 0))
        .join(Deal, Deal.assigned_to_id == User.id)
        .filter(Deal.company_id == company.id, Deal.stage == "won", Deal.closed_at >= start, Deal.closed_at <= end)
        .group_by(User.name)
        .order_by(func.coalesce(func.sum(Deal.expected_value), 0).desc())
        .all()
    ):
        by_owner.append(SalesReportRankRow(name=name, count=cnt, value=_float(val)))

    by_customer = []
    for name, cnt, val in (
        db.query(Contact.name, func.count(Deal.id), func.coalesce(func.sum(Deal.expected_value), 0))
        .join(Deal, Deal.contact_id == Contact.id)
        .filter(Deal.company_id == company.id, Deal.stage == "won", Deal.closed_at >= start, Deal.closed_at <= end)
        .group_by(Contact.name)
        .order_by(func.coalesce(func.sum(Deal.expected_value), 0).desc())
        .limit(10)
        .all()
    ):
        by_customer.append(SalesReportRankRow(name=name or "Unknown", count=cnt, value=_float(val)))

    by_source = []
    for source, val in (
        db.query(Lead.source, func.coalesce(func.sum(Deal.expected_value), 0))
        .join(Deal, Deal.lead_id == Lead.id)
        .filter(Deal.company_id == company.id, Deal.stage == "won", Deal.closed_at >= start, Deal.closed_at <= end)
        .group_by(Lead.source)
        .order_by(func.coalesce(func.sum(Deal.expected_value), 0).desc())
        .all()
    ):
        by_source.append(SalesReportRankRow(name=source or "Unknown", value=_float(val)))

    return SalesReportRevenueResponse(
        period_label=period_label,
        booked_revenue=booked,
        collected_revenue=collected,
        outstanding_revenue=outstanding,
        pipeline_forecast=pipeline,
        avg_deal_size=round(avg_deal, 0),
        trend=trend,
        by_owner=by_owner,
        by_customer=by_customer,
        by_source=by_source,
        previous_booked_revenue=prev_booked if prev_booked else None,
    )


@router.get("/lead-sources", response_model=SalesReportLeadSourceResponse)
def lead_source_report(
    period: str = Query("month"),
    owner_id: int | None = None,
    user: User = Depends(require_permission("reports.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    owner_id = _resolve_owner_filter(user, db, owner_id)
    start, end, _, _, period_label = _period_bounds(period, None, None)

    sources = []
    for source, lead_cnt in (
        _lead_owner_filter(
            db.query(Lead.source, func.count(Lead.id)).filter(
                Lead.company_id == company.id, Lead.created_at >= start, Lead.created_at <= end
            ),
            owner_id,
        )
        .group_by(Lead.source)
        .all()
    ):
        won_val = (
            db.query(func.coalesce(func.sum(Deal.expected_value), 0))
            .join(Lead, Deal.lead_id == Lead.id)
            .filter(
                Lead.company_id == company.id,
                Lead.source == source,
                Deal.stage == "won",
                Deal.closed_at >= start,
                Deal.closed_at <= end,
            )
            .scalar()
        )
        deal_cnt = (
            db.query(func.count(Deal.id))
            .join(Lead, Deal.lead_id == Lead.id)
            .filter(Lead.company_id == company.id, Lead.source == source, Deal.created_at >= start, Deal.created_at <= end)
            .scalar()
            or 0
        )
        rate = _rate(deal_cnt, lead_cnt)
        badge = "Strong Source" if rate >= 30 else ("Weak Source" if rate < 10 and lead_cnt >= 5 else None)
        sources.append(SalesReportRankRow(name=source or "Unknown", count=lead_cnt, value=_float(won_val), rate=rate, badge=badge))

    sources.sort(key=lambda s: (s.rate or 0, s.value), reverse=True)
    chart = [SalesReportTrendPoint(label=s.name, value=s.rate or 0) for s in sources[:8]]

    return SalesReportLeadSourceResponse(period_label=period_label, sources=sources, conversion_chart=chart)


@router.get("/executives", response_model=SalesReportExecutiveResponse)
def executive_report(
    period: str = Query("month"),
    user: User = Depends(require_permission("reports.view_team")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    start, end, _, _, period_label = _period_bounds(period, None, None)

    staff = db.query(User).filter(User.role.in_(STAFF_ROLES), User.status == "active").all()
    executives = []
    detail = []

    for u in staff:
        leads_handled = db.query(Lead).filter(
            Lead.company_id == company.id, Lead.assigned_to_id == u.id, Lead.created_at >= start, Lead.created_at <= end
        ).count()
        deals_created = db.query(Deal).filter(
            Deal.company_id == company.id, Deal.assigned_to_id == u.id, Deal.created_at >= start, Deal.created_at <= end
        ).count()
        won_deals = db.query(Deal).filter(
            Deal.company_id == company.id,
            Deal.assigned_to_id == u.id,
            Deal.stage == "won",
            Deal.closed_at >= start,
            Deal.closed_at <= end,
        ).all()
        won_count = len(won_deals)
        revenue = sum(_float(d.expected_value) for d in won_deals)
        pending = db.query(Deal).filter(
            Deal.company_id == company.id, Deal.assigned_to_id == u.id, Deal.stage.in_(PIPELINE_STAGES)
        ).count()
        win_rate = _rate(won_count, deals_created)
        avg_size = revenue / won_count if won_count else 0
        badge = "High Performer" if win_rate >= 40 and revenue > 0 else ("Underperforming" if deals_created >= 3 and win_rate < 15 else None)

        executives.append(SalesReportRankRow(
            id=u.id, name=u.name, count=deals_created, value=revenue, rate=win_rate, badge=badge,
        ))
        detail.append({
            "id": u.id,
            "name": u.name,
            "leads_handled": leads_handled,
            "deals_created": deals_created,
            "won_count": won_count,
            "win_rate": win_rate,
            "revenue_closed": revenue,
            "avg_deal_size": round(avg_size, 0),
            "pending_deals": pending,
        })

    executives.sort(key=lambda e: e.value, reverse=True)
    return SalesReportExecutiveResponse(period_label=period_label, executives=executives, detail=detail)


@router.get("/pending-deals", response_model=SalesReportPendingDealsResponse)
def pending_deals_report(
    owner_id: int | None = None,
    user: User = Depends(require_permission("reports.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    owner_id = _resolve_owner_filter(user, db, owner_id)
    _, _, _, _, period_label = _period_bounds("month", None, None)

    deals = (
        db.query(Deal)
        .options(joinedload(Deal.assigned_to))
        .filter(Deal.company_id == company.id, Deal.stage.in_(PIPELINE_STAGES))
    )
    deals = _deal_owner_filter(deals, owner_id).all()

    rows = [_pending_deal_row(d) for d in deals]
    rows.sort(key=lambda r: (r.is_overdue, r.is_stale, r.expected_value), reverse=True)

    total_value = sum(r.expected_value for r in rows)
    overdue_count = sum(1 for r in rows if r.is_overdue)
    stale_count = sum(1 for r in rows if r.is_stale)

    buckets = {"0-7d": 0, "8-14d": 0, "15-30d": 0, "30d+": 0}
    for r in rows:
        if r.days_stale <= 7:
            buckets["0-7d"] += 1
        elif r.days_stale <= 14:
            buckets["8-14d"] += 1
        elif r.days_stale <= 30:
            buckets["15-30d"] += 1
        else:
            buckets["30d+"] += 1

    return SalesReportPendingDealsResponse(
        period_label=period_label,
        total_count=len(rows),
        total_value=total_value,
        overdue_count=overdue_count,
        stale_count=stale_count,
        aging_buckets=[SalesReportTrendPoint(label=k, value=v) for k, v in buckets.items()],
        deals=rows,
    )


@router.get("/pipeline-health", response_model=SalesReportPipelineHealthResponse)
def pipeline_health_report(
    owner_id: int | None = None,
    user: User = Depends(require_permission("reports.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    owner_id = _resolve_owner_filter(user, db, owner_id)
    _, _, _, _, period_label = _period_bounds("month", None, None)
    now = datetime.now(timezone.utc)

    stages = []
    total_value = 0.0
    all_open = []

    for stage in PIPELINE_STAGES:
        stage_deals = _deal_owner_filter(
            db.query(Deal).filter(Deal.company_id == company.id, Deal.stage == stage),
            owner_id,
        ).all()
        val = sum(_float(d.expected_value) for d in stage_deals)
        total_value += val
        all_open.extend(stage_deals)
        ages = [(now - (d.updated_at or d.created_at)).days for d in stage_deals if d.updated_at or d.created_at]
        avg_age = sum(ages) / len(ages) if ages else 0
        stages.append(SalesReportPipelineStage(
            stage=stage,
            label=DEAL_STAGE_LABELS.get(stage, stage),
            count=len(stage_deals),
            value=val,
            avg_age_days=round(avg_age, 1),
        ))

    top_deal = max((_float(d.expected_value) for d in all_open), default=0)
    concentration = (top_deal / total_value * 100) if total_value > 0 else 0

    stale_ratio = sum(1 for d in all_open if (now - (d.updated_at or d.created_at)).days >= STALE_DEAL_DAYS) / max(len(all_open), 1)
    health_score = max(0, min(100, int(100 - stale_ratio * 40 - concentration * 0.3)))
    health_label = "On Track" if health_score >= 70 else ("At Risk" if health_score >= 40 else "Needs Attention")

    return SalesReportPipelineHealthResponse(
        period_label=period_label,
        stages=stages,
        total_pipeline_value=total_value,
        concentration_top_deal_percent=round(concentration, 1),
        health_score=health_score,
        health_label=health_label,
    )
