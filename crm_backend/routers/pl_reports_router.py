from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_current_user, get_db
from expense_config import EXPENSE_CATEGORY_LABELS, EXPENSE_STATUS_LABELS
from invoice_config import INVOICE_STATUS_LABELS
from models import Company, Expense, Invoice, User, VendorBill
from permissions import role_has_permission
from pl_reports_config import (
    BILL_DRAFT_STATUSES,
    CREDIT_INVOICE_TYPES,
    EXCLUDED_INVOICE_TYPES,
    EXPENSE_DRAFT_STATUSES,
    EXPENSE_STATUSES,
    GROSS_SALES_INVOICE_TYPES,
    INVOICE_DRAFT_STATUSES,
    INVOICE_TYPE_LABELS,
    PERIOD_LABELS,
    PURCHASE_BILL_STATUSES,
    REPORT_PERIODS,
    REVENUE_INVOICE_STATUSES,
)
from schemas import (
    PLReportCategoryRow,
    PLReportCompanyContext,
    PLReportComparisonMetric,
    PLReportCostRegisterRow,
    PLReportCostsResponse,
    PLReportDataQuality,
    PLReportExcludedExpenseRow,
    PLReportExpenseRegisterRow,
    PLReportExpensesResponse,
    PLReportExportLogRequest,
    PLReportPeriodOption,
    PLReportRevenueRegisterRow,
    PLReportRevenueResponse,
    PLReportStatementLine,
    PLReportSummaryResponse,
    PLReportTrendPoint,
)
from vendor_bills_config import VENDOR_BILL_STATUS_LABELS

router = APIRouter(prefix="/pl-reports", tags=["pl-reports"])


def _float(v) -> float:
    return 0.0 if v is None else float(v)




def _has_any_permission(db: Session, role: str, codes: tuple[str, ...]) -> bool:
    return any(role_has_permission(db, role, code) for code in codes)


def _require_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(db, user.role, ("pl_reports.view", "reports.view_financial")):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_export(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(db, user.role, ("pl_reports.export", "reports.export")):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _company_context(company: Company) -> PLReportCompanyContext:
    return PLReportCompanyContext(
        company_name=company.legal_name or company.display_name or "Company",
        currency=company.currency or "INR",
    )


def _fy_start_year(now: datetime, fy_start_month: int) -> int:
    if now.month >= fy_start_month:
        return now.year
    return now.year - 1


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _month_end(year: int, month: int) -> datetime:
    last_day = monthrange(year, month)[1]
    return datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc)


def _period_bounds(
    period: str,
    date_from: datetime | None,
    date_to: datetime | None,
    fy_start_month: int = 4,
) -> tuple[datetime, datetime, str]:
    now = datetime.now(timezone.utc)

    if period == "custom":
        if not date_from or not date_to:
            raise HTTPException(status_code=400, detail="Custom period requires date_from and date_to")
        start = date_from if date_from.tzinfo else date_from.replace(tzinfo=timezone.utc)
        end = date_to if date_to.tzinfo else date_to.replace(tzinfo=timezone.utc)
        if end < start:
            raise HTTPException(status_code=400, detail="date_to must be on or after date_from")
        return start, end, PERIOD_LABELS.get(period, period)

    if period == "month":
        start = _month_start(now.year, now.month)
        end = now
        return start, end, PERIOD_LABELS[period]

    if period == "last_month":
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
        start = _month_start(year, month)
        end = _month_end(year, month)
        return start, end, PERIOD_LABELS[period]

    if period == "quarter":
        fy_year = _fy_start_year(now, fy_start_month)
        fy_start = _month_start(fy_year, fy_start_month)
        months_since = (now.year - fy_start.year) * 12 + (now.month - fy_start.month)
        quarter_index = months_since // 3
        q_start_month = fy_start_month + quarter_index * 3
        q_start_year = fy_year
        while q_start_month > 12:
            q_start_month -= 12
            q_start_year += 1
        start = _month_start(q_start_year, q_start_month)
        end = now
        return start, end, PERIOD_LABELS[period]

    if period == "financial_year":
        fy_year = _fy_start_year(now, fy_start_month)
        start = _month_start(fy_year, fy_start_month)
        end = now
        label = f"FY {fy_year}-{str(fy_year + 1)[-2:]}"
        return start, end, label

    if period == "last_financial_year":
        current_fy_year = _fy_start_year(now, fy_start_month)
        prev_fy_year = current_fy_year - 1
        start = _month_start(prev_fy_year, fy_start_month)
        end_month = fy_start_month - 1 if fy_start_month > 1 else 12
        end_year = prev_fy_year if fy_start_month > 1 else prev_fy_year + 1
        end = _month_end(end_year, end_month)
        label = f"FY {prev_fy_year}-{str(prev_fy_year + 1)[-2:]}"
        return start, end, label

    raise HTTPException(status_code=400, detail=f"Period must be one of: {', '.join(REPORT_PERIODS)}")


def _comparison_bounds(
    period: str,
    date_from: datetime | None,
    date_to: datetime | None,
    fy_start_month: int = 4,
) -> tuple[datetime, datetime, str]:
    now = datetime.now(timezone.utc)

    if period == "custom":
        if not date_from or not date_to:
            raise HTTPException(status_code=400, detail="Custom period requires date_from and date_to")
        start = date_from if date_from.tzinfo else date_from.replace(tzinfo=timezone.utc)
        end = date_to if date_to.tzinfo else date_to.replace(tzinfo=timezone.utc)
        duration = end - start
        prev_end = start - timedelta(microseconds=1)
        prev_start = prev_end - duration
        return prev_start, prev_end, "Previous period"

    if period == "month":
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
        start = _month_start(year, month)
        end = _month_end(year, month)
        return start, end, PERIOD_LABELS["last_month"]

    if period == "last_month":
        if now.month <= 2:
            year, month = now.year - 1, now.month + 10
        else:
            year, month = now.year, now.month - 2
        start = _month_start(year, month)
        end = _month_end(year, month)
        return start, end, "Prior month"

    if period == "quarter":
        current_start, _, _ = _period_bounds("quarter", None, None, fy_start_month)
        prev_end = current_start - timedelta(microseconds=1)
        prev_start_month = current_start.month - 3
        prev_start_year = current_start.year
        while prev_start_month <= 0:
            prev_start_month += 12
            prev_start_year -= 1
        prev_start = _month_start(prev_start_year, prev_start_month)
        return prev_start, prev_end, "Previous quarter"

    if period == "financial_year":
        return _period_bounds("last_financial_year", None, None, fy_start_month)

    if period == "last_financial_year":
        current_fy_year = _fy_start_year(now, fy_start_month)
        prev_fy_year = current_fy_year - 2
        start = _month_start(prev_fy_year, fy_start_month)
        end_month = fy_start_month - 1 if fy_start_month > 1 else 12
        end_year = prev_fy_year if fy_start_month > 1 else prev_fy_year + 1
        end = _month_end(end_year, end_month)
        label = f"FY {prev_fy_year}-{str(prev_fy_year + 1)[-2:]}"
        return start, end, label

    raise HTTPException(status_code=400, detail=f"Period must be one of: {', '.join(REPORT_PERIODS)}")


def _margin_pct(profit: float, revenue: float) -> float | None:
    if revenue <= 0:
        return None
    return round(profit / revenue * 100, 1)


def _change_pct(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def _comparison_metric(key: str, label: str, current: float, previous: float) -> PLReportComparisonMetric:
    change = round(current - previous, 2)
    return PLReportComparisonMetric(
        key=key,
        label=label,
        current=round(current, 2),
        previous=round(previous, 2),
        change_amount=change,
        change_pct=_change_pct(current, previous),
    )


def _revenue_query(db: Session, company_id: int, start: datetime, end: datetime, search: str | None = None):
    q = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(REVENUE_INVOICE_STATUSES),
            Invoice.invoice_type.notin_(EXCLUDED_INVOICE_TYPES),
            Invoice.issue_date.isnot(None),
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
        )
    )
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            (Invoice.invoice_number.ilike(term))
            | (Invoice.client_name.ilike(term))
            | (Invoice.client_org.ilike(term))
        )
    return q.order_by(Invoice.issue_date.desc(), Invoice.id.desc())


def _costs_query(db: Session, company_id: int, start: datetime, end: datetime, search: str | None = None):
    q = (
        db.query(VendorBill)
        .options(joinedload(VendorBill.purchase_order))
        .filter(
            VendorBill.company_id == company_id,
            VendorBill.status.in_(PURCHASE_BILL_STATUSES),
            VendorBill.bill_date >= start,
            VendorBill.bill_date <= end,
        )
    )
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            (VendorBill.bill_number.ilike(term))
            | (VendorBill.supplier_invoice_number.ilike(term))
            | (VendorBill.vendor_name.ilike(term))
        )
    return q.order_by(VendorBill.bill_date.desc(), VendorBill.id.desc())


def _expenses_query(db: Session, company_id: int, start: datetime, end: datetime, search: str | None = None):
    q = (
        db.query(Expense)
        .options(joinedload(Expense.submitted_by))
        .filter(
            Expense.company_id == company_id,
            Expense.status.in_(EXPENSE_STATUSES),
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
    )
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            (Expense.expense_number.ilike(term))
            | (Expense.title.ilike(term))
            | (Expense.vendor_name.ilike(term))
            | (Expense.category.ilike(term))
        )
    return q.order_by(Expense.expense_date.desc(), Expense.id.desc())


def _linked_expense_ids(db: Session, company_id: int, start: datetime, end: datetime) -> set[int]:
    rows = (
        db.query(VendorBill.expense_id)
        .filter(
            VendorBill.company_id == company_id,
            VendorBill.status.in_(PURCHASE_BILL_STATUSES),
            VendorBill.bill_date >= start,
            VendorBill.bill_date <= end,
            VendorBill.expense_id.isnot(None),
        )
        .all()
    )
    return {row[0] for row in rows if row[0]}


def _compute_metrics(
    db: Session,
    company_id: int,
    start: datetime,
    end: datetime,
    default_currency: str,
) -> dict:
    invoices = _revenue_query(db, company_id, start, end).all()
    gross_sales = 0.0
    credit_notes = 0.0
    write_off_total = 0.0
    mixed_currency = False
    for inv in invoices:
        if inv.currency and inv.currency != default_currency:
            mixed_currency = True
        sub = _float(inv.subtotal)
        if inv.invoice_type in CREDIT_INVOICE_TYPES:
            credit_notes += sub
        elif inv.invoice_type in GROSS_SALES_INVOICE_TYPES:
            gross_sales += sub
        write_off_total += _float(inv.write_off_amount)

    bills = _costs_query(db, company_id, start, end).all()
    purchases = 0.0
    for bill in bills:
        if bill.currency and bill.currency != default_currency:
            mixed_currency = True
        purchases += _float(bill.subtotal)

    linked_ids = _linked_expense_ids(db, company_id, start, end)
    expenses = _expenses_query(db, company_id, start, end).all()
    operating = 0.0
    by_category: dict[str, float] = defaultdict(float)
    dedup_count = 0
    dedup_amount = 0.0
    for exp in expenses:
        if exp.currency and exp.currency != default_currency:
            mixed_currency = True
        if exp.id in linked_ids:
            dedup_count += 1
            dedup_amount += _float(exp.amount)
            continue
        amt = _float(exp.amount)
        operating += amt
        by_category[exp.category] += amt

    net_revenue = round(gross_sales - credit_notes, 2)
    purchases = round(purchases, 2)
    operating = round(operating, 2)
    gross_profit = round(net_revenue - purchases, 2)
    net_profit = round(gross_profit - operating, 2)

    return {
        "gross_sales": round(gross_sales, 2),
        "credit_notes": round(credit_notes, 2),
        "net_revenue": net_revenue,
        "purchases_costs": purchases,
        "gross_profit": gross_profit,
        "gross_margin_pct": _margin_pct(gross_profit, net_revenue),
        "operating_expenses": operating,
        "net_profit": net_profit,
        "net_margin_pct": _margin_pct(net_profit, net_revenue),
        "write_off_total": round(write_off_total, 2),
        "deduplicated_expense_count": dedup_count,
        "deduplicated_expense_amount": round(dedup_amount, 2),
        "expense_by_category": by_category,
        "mixed_currency": mixed_currency,
        "invoice_count": len(invoices),
        "bill_count": len(bills),
        "expense_count": len(expenses) - dedup_count,
    }


def _data_quality(db: Session, company_id: int, start: datetime, end: datetime, metrics: dict) -> PLReportDataQuality:
    excluded_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(INVOICE_DRAFT_STATUSES),
            Invoice.issue_date.isnot(None),
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
        )
        .count()
    )
    excluded_bills = (
        db.query(VendorBill)
        .filter(
            VendorBill.company_id == company_id,
            VendorBill.status.in_(BILL_DRAFT_STATUSES),
            VendorBill.bill_date >= start,
            VendorBill.bill_date <= end,
        )
        .count()
    )
    excluded_expenses = (
        db.query(Expense)
        .filter(
            Expense.company_id == company_id,
            Expense.status.in_(EXPENSE_DRAFT_STATUSES),
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
        .count()
    )
    return PLReportDataQuality(
        excluded_draft_invoices=excluded_invoices,
        excluded_draft_bills=excluded_bills,
        excluded_draft_expenses=excluded_expenses,
        deduplicated_expense_count=metrics["deduplicated_expense_count"],
        deduplicated_expense_amount=metrics["deduplicated_expense_amount"],
        write_off_total=metrics["write_off_total"],
        mixed_currency=metrics["mixed_currency"],
    )


def _trend_points(db: Session, company_id: int, default_currency: str, months: int = 6) -> list[PLReportTrendPoint]:
    now = datetime.now(timezone.utc)
    points: list[PLReportTrendPoint] = []
    year, month = now.year, now.month
    for offset in range(months - 1, -1, -1):
        m = month - offset
        y = year
        while m <= 0:
            m += 12
            y -= 1
        start = _month_start(y, m)
        end = _month_end(y, m) if (y, m) != (now.year, now.month) else now
        metrics = _compute_metrics(db, company_id, start, end, default_currency)
        label = start.strftime("%b %Y")
        points.append(
            PLReportTrendPoint(
                period_label=label,
                net_revenue=metrics["net_revenue"],
                gross_profit=metrics["gross_profit"],
                net_profit=metrics["net_profit"],
            )
        )
    return points


def _paginate(query, page: int, per_page: int):
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return rows, total, page, per_page


def _resolve_period(
    period: str,
    date_from: datetime | None,
    date_to: datetime | None,
    fy_start_month: int,
) -> tuple[datetime, datetime, str, datetime, datetime, str]:
    start, end, label = _period_bounds(period, date_from, date_to, fy_start_month)
    comp_start, comp_end, comp_label = _comparison_bounds(period, date_from, date_to, fy_start_month)
    return start, end, label, comp_start, comp_end, comp_label


@router.get("/periods", response_model=list[PLReportPeriodOption])
def list_periods(_user: User = Depends(_require_view)):
    return [PLReportPeriodOption(key=k, label=PERIOD_LABELS[k]) for k in REPORT_PERIODS]


@router.get("/summary", response_model=PLReportSummaryResponse)
def pl_summary(
    period: str = Query(default="month"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    fy = company.financial_year_start_month or 4
    start, end, label, comp_start, comp_end, comp_label = _resolve_period(period, date_from, date_to, fy)
    ctx = _company_context(company)

    current = _compute_metrics(db, company.id, start, end, ctx.currency)
    previous = _compute_metrics(db, company.id, comp_start, comp_end, ctx.currency)
    quality = _data_quality(db, company.id, start, end, current)

    statement = [
        PLReportStatementLine(key="gross_sales", label="Gross sales", current=current["gross_sales"], previous=previous["gross_sales"]),
        PLReportStatementLine(key="credit_notes", label="Credit notes", current=current["credit_notes"], previous=previous["credit_notes"]),
        PLReportStatementLine(key="net_revenue", label="Net revenue", current=current["net_revenue"], previous=previous["net_revenue"], is_total=True),
        PLReportStatementLine(key="purchases_costs", label="Purchases / direct costs", current=current["purchases_costs"], previous=previous["purchases_costs"]),
        PLReportStatementLine(key="gross_profit", label="Gross profit", current=current["gross_profit"], previous=previous["gross_profit"], is_total=True),
        PLReportStatementLine(key="operating_expenses", label="Operating expenses", current=current["operating_expenses"], previous=previous["operating_expenses"]),
        PLReportStatementLine(key="net_profit", label="Net profit", current=current["net_profit"], previous=previous["net_profit"], is_total=True),
    ]

    comparisons = [
        _comparison_metric("net_revenue", "Net revenue", current["net_revenue"], previous["net_revenue"]),
        _comparison_metric("gross_profit", "Gross profit", current["gross_profit"], previous["gross_profit"]),
        _comparison_metric("operating_expenses", "Operating expenses", current["operating_expenses"], previous["operating_expenses"]),
        _comparison_metric("net_profit", "Net profit", current["net_profit"], previous["net_profit"]),
    ]

    categories = [
        PLReportCategoryRow(
            category=k,
            category_label=EXPENSE_CATEGORY_LABELS.get(k, k.replace("_", " ").title()),
            amount=round(v, 2),
        )
        for k, v in sorted(current["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
    ]

    return PLReportSummaryResponse(
        period=period,
        period_label=label,
        date_from=start,
        date_to=end,
        comparison_period_label=comp_label,
        comparison_date_from=comp_start,
        comparison_date_to=comp_end,
        company=ctx,
        gross_sales=current["gross_sales"],
        credit_notes=current["credit_notes"],
        net_revenue=current["net_revenue"],
        purchases_costs=current["purchases_costs"],
        gross_profit=current["gross_profit"],
        gross_margin_pct=current["gross_margin_pct"],
        operating_expenses=current["operating_expenses"],
        net_profit=current["net_profit"],
        net_margin_pct=current["net_margin_pct"],
        previous_gross_sales=previous["gross_sales"],
        previous_credit_notes=previous["credit_notes"],
        previous_net_revenue=previous["net_revenue"],
        previous_purchases_costs=previous["purchases_costs"],
        previous_gross_profit=previous["gross_profit"],
        previous_operating_expenses=previous["operating_expenses"],
        previous_net_profit=previous["net_profit"],
        comparisons=comparisons,
        statement=statement,
        expense_categories=categories,
        trend=_trend_points(db, company.id, ctx.currency),
        data_quality=quality,
    )


@router.get("/revenue", response_model=PLReportRevenueResponse)
def pl_revenue(
    period: str = Query(default="month"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    fy = company.financial_year_start_month or 4
    start, end, label, _, _, _ = _resolve_period(period, date_from, date_to, fy)
    ctx = _company_context(company)
    metrics = _compute_metrics(db, company.id, start, end, ctx.currency)

    query = _revenue_query(db, company.id, start, end, search)
    rows, total, page, per_page = _paginate(query, page, per_page)

    register = []
    for inv in rows:
        is_credit = inv.invoice_type in CREDIT_INVOICE_TYPES
        register.append(
            PLReportRevenueRegisterRow(
                id=inv.id,
                invoice_number=inv.invoice_number,
                issue_date=inv.issue_date,
                client_name=inv.client_org or inv.client_name,
                invoice_type=inv.invoice_type,
                invoice_type_label=INVOICE_TYPE_LABELS.get(inv.invoice_type, inv.invoice_type),
                subtotal=_float(inv.subtotal),
                total_tax=_float(inv.total_tax),
                grand_total=_float(inv.grand_total),
                status=inv.status,
                status_label=INVOICE_STATUS_LABELS.get(inv.status, inv.status),
                is_credit_note=is_credit,
            )
        )

    return PLReportRevenueResponse(
        period=period,
        period_label=label,
        date_from=start,
        date_to=end,
        company=ctx,
        gross_sales=metrics["gross_sales"],
        credit_notes=metrics["credit_notes"],
        net_revenue=metrics["net_revenue"],
        register=register,
        register_total=total,
        register_page=page,
        register_per_page=per_page,
        data_quality=_data_quality(db, company.id, start, end, metrics),
    )


@router.get("/costs", response_model=PLReportCostsResponse)
def pl_costs(
    period: str = Query(default="month"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    fy = company.financial_year_start_month or 4
    start, end, label, _, _, _ = _resolve_period(period, date_from, date_to, fy)
    ctx = _company_context(company)
    metrics = _compute_metrics(db, company.id, start, end, ctx.currency)

    query = _costs_query(db, company.id, start, end, search)
    rows, total, page, per_page = _paginate(query, page, per_page)

    register = []
    for bill in rows:
        po_number = bill.purchase_order.po_number if bill.purchase_order else None
        register.append(
            PLReportCostRegisterRow(
                id=bill.id,
                bill_number=bill.bill_number,
                supplier_invoice_number=bill.supplier_invoice_number,
                bill_date=bill.bill_date,
                vendor_name=bill.vendor_name,
                subtotal=_float(bill.subtotal),
                total_tax=_float(bill.total_tax),
                grand_total=_float(bill.grand_total),
                status=bill.status,
                status_label=VENDOR_BILL_STATUS_LABELS.get(bill.status, bill.status),
                purchase_order_id=bill.purchase_order_id,
                po_number=po_number,
                expense_id=bill.expense_id,
                expense_linked=bill.expense_id is not None,
            )
        )

    return PLReportCostsResponse(
        period=period,
        period_label=label,
        date_from=start,
        date_to=end,
        company=ctx,
        purchases_costs=metrics["purchases_costs"],
        register=register,
        register_total=total,
        register_page=page,
        register_per_page=per_page,
        data_quality=_data_quality(db, company.id, start, end, metrics),
    )


@router.get("/expenses", response_model=PLReportExpensesResponse)
def pl_expenses(
    period: str = Query(default="month"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    fy = company.financial_year_start_month or 4
    start, end, label, _, _, _ = _resolve_period(period, date_from, date_to, fy)
    ctx = _company_context(company)
    metrics = _compute_metrics(db, company.id, start, end, ctx.currency)
    linked_ids = _linked_expense_ids(db, company.id, start, end)

    query = _expenses_query(db, company.id, start, end, search)
    all_rows = query.all()

    included_rows = []
    excluded_rows: list[PLReportExcludedExpenseRow] = []
    for exp in all_rows:
        if exp.id in linked_ids:
            excluded_rows.append(
                PLReportExcludedExpenseRow(
                    id=exp.id,
                    expense_number=exp.expense_number,
                    expense_date=exp.expense_date,
                    title=exp.title,
                    vendor_name=exp.vendor_name,
                    amount=_float(exp.amount),
                    exclusion_reason="Linked to vendor bill in period",
                )
            )
            continue
        included_rows.append(exp)

    total = len(included_rows)
    page_rows = included_rows[(page - 1) * per_page : page * per_page]

    register = []
    for exp in page_rows:
        register.append(
            PLReportExpenseRegisterRow(
                id=exp.id,
                expense_number=exp.expense_number,
                expense_date=exp.expense_date,
                category=exp.category,
                category_label=EXPENSE_CATEGORY_LABELS.get(exp.category, exp.category),
                title=exp.title,
                vendor_name=exp.vendor_name,
                amount=_float(exp.amount),
                status=exp.status,
                status_label=EXPENSE_STATUS_LABELS.get(exp.status, exp.status),
                submitter_name=exp.submitted_by.name if exp.submitted_by else None,
                included_in_pl=True,
                exclusion_reason=None,
            )
        )

    categories = [
        PLReportCategoryRow(
            category=k,
            category_label=EXPENSE_CATEGORY_LABELS.get(k, k.replace("_", " ").title()),
            amount=round(v, 2),
        )
        for k, v in sorted(metrics["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
    ]

    return PLReportExpensesResponse(
        period=period,
        period_label=label,
        date_from=start,
        date_to=end,
        company=ctx,
        operating_expenses=metrics["operating_expenses"],
        expense_categories=categories,
        register=register,
        excluded_duplicates=excluded_rows,
        register_total=total,
        register_page=page,
        register_per_page=per_page,
        data_quality=_data_quality(db, company.id, start, end, metrics),
    )


@router.post("/export-log")
def export_log(
    payload: PLReportExportLogRequest,
    request: Request,
    user: User = Depends(_require_export),
    db: Session = Depends(get_db),
):
    log_activity(
        db,
        user_id=user.id,
        action="pl_report_exported",
        entity_type="pl_report",
        entity_id=0,
        details={
            "report_type": payload.report_type,
            "period": payload.period,
            "period_label": payload.period_label,
            "row_count": payload.row_count,
        },
        ip_address=get_client_ip(request),
    )
    return {"ok": True}
