from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_current_user, get_db
from invoice_config import INVOICE_STATUS_LABELS
from models import Company, Invoice, User, VendorBill
from permissions import role_has_permission
from schemas import (
    TaxReportCompanyContext,
    TaxReportDataQuality,
    TaxReportExportLogRequest,
    TaxReportInwardRegisterRow,
    TaxReportOverviewResponse,
    TaxReportOutwardRegisterRow,
    TaxReportPeriodOption,
    TaxReportPurchaseResponse,
    TaxReportRateRow,
    TaxReportSalesResponse,
    TaxReportSummaryResponse,
    TaxReportVendorSummaryRow,
)
from tax_reports_config import (
    GSTIN_PATTERN,
    INWARD_DRAFT_STATUSES,
    INWARD_STATUSES,
    OUTWARD_DRAFT_STATUSES,
    OUTWARD_STATUSES,
    PERIOD_LABELS,
    REPORT_PERIODS,
    STANDARD_RATES,
)
from vendor_bills_config import VENDOR_BILL_STATUS_LABELS

router = APIRouter(prefix="/tax-reports", tags=["tax-reports"])


def _float(v) -> float:
    return 0.0 if v is None else float(v)




def _has_any_permission(db: Session, role: str, codes: tuple[str, ...]) -> bool:
    return any(role_has_permission(db, role, code) for code in codes)


def _require_tax_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(db, user.role, ("tax_reports.view", "reports.view_financial")):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_sales_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(
        db,
        user.role,
        ("tax_reports.view_sales", "tax_reports.view", "reports.view_financial"),
    ):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_purchase_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(
        db,
        user.role,
        ("tax_reports.view_purchase", "tax_reports.view", "reports.view_financial"),
    ):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_summary_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(
        db,
        user.role,
        ("tax_reports.view_summary", "tax_reports.view", "reports.view_financial"),
    ):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_export(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(db, user.role, ("tax_reports.export", "reports.export")):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _valid_gstin(gstin: str | None) -> bool:
    if not gstin or not str(gstin).strip():
        return False
    return bool(GSTIN_PATTERN.match(str(gstin).strip().upper()))


def _company_context(company: Company) -> TaxReportCompanyContext:
    gstin = company.gstin.strip().upper() if company.gstin else None
    return TaxReportCompanyContext(
        company_name=company.legal_name or company.display_name or "Company",
        gstin=gstin,
        gstin_configured=_valid_gstin(gstin),
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


def _rate_label(rate: float) -> str:
    if rate == 0:
        return "Exempt / 0%"
    if rate in STANDARD_RATES:
        return f"{rate:g}%"
    return f"{rate:g}% (other)"


def _bucket_rate(rate: float) -> float:
    r = round(rate, 2)
    if r in STANDARD_RATES:
        return r
    return -1.0


def _line_tax(line_subtotal, tax_rate) -> float:
    sub = _float(line_subtotal)
    rate = _float(tax_rate)
    return round(sub * rate / 100, 2)


def _tax_rate_summary(line_items) -> str:
    rates = sorted({round(_float(li.tax_rate), 2) for li in line_items})
    if not rates:
        return "—"
    if len(rates) == 1:
        return _rate_label(rates[0])
    return "Mixed"


def _aggregate_rate_breakdown(documents, line_items_attr: str) -> list[TaxReportRateRow]:
    buckets: dict[float, dict] = defaultdict(lambda: {"taxable": 0.0, "tax": 0.0, "docs": set()})

    for doc in documents:
        for li in getattr(doc, line_items_attr, []) or []:
            bucket = _bucket_rate(_float(li.tax_rate))
            taxable = _float(li.line_subtotal)
            tax = _line_tax(li.line_subtotal, li.tax_rate)
            buckets[bucket]["taxable"] += taxable
            buckets[bucket]["tax"] += tax
            buckets[bucket]["docs"].add(doc.id)

    rows: list[TaxReportRateRow] = []
    ordered_keys = [r for r in STANDARD_RATES if r in buckets]
    if -1.0 in buckets:
        ordered_keys.append(-1.0)
    for key in ordered_keys:
        data = buckets[key]
        display_rate = 0.0 if key == -1.0 else key
        label = "Other rates" if key == -1.0 else _rate_label(key)
        rows.append(
            TaxReportRateRow(
                rate=display_rate if key != -1.0 else -1.0,
                rate_label=label,
                taxable_value=round(data["taxable"], 2),
                tax_amount=round(data["tax"], 2),
                document_count=len(data["docs"]),
            )
        )
    return rows


def _merge_rate_breakdown(outward_rows: list[TaxReportRateRow], inward_rows: list[TaxReportRateRow]) -> list[TaxReportRateRow]:
    merged: dict[str, TaxReportRateRow] = {}
    for row in outward_rows + inward_rows:
        key = row.rate_label
        if key not in merged:
            merged[key] = TaxReportRateRow(
                rate=row.rate,
                rate_label=row.rate_label,
                taxable_value=0.0,
                tax_amount=0.0,
                document_count=0,
            )
        merged[key].taxable_value = round(merged[key].taxable_value + row.taxable_value, 2)
        merged[key].tax_amount = round(merged[key].tax_amount + row.tax_amount, 2)
        merged[key].document_count += row.document_count
    return list(merged.values())


def _outward_query(db: Session, company_id: int, start: datetime, end: datetime, search: str | None = None):
    q = (
        db.query(Invoice)
        .options(joinedload(Invoice.line_items))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(OUTWARD_STATUSES),
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
            | (Invoice.client_gstin.ilike(term))
        )
    return q.order_by(Invoice.issue_date.desc(), Invoice.id.desc())


def _inward_query(db: Session, company_id: int, start: datetime, end: datetime, search: str | None = None):
    q = (
        db.query(VendorBill)
        .options(joinedload(VendorBill.line_items), joinedload(VendorBill.purchase_order))
        .filter(
            VendorBill.company_id == company_id,
            VendorBill.status.in_(INWARD_STATUSES),
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
            | (VendorBill.vendor_gstin.ilike(term))
        )
    return q.order_by(VendorBill.bill_date.desc(), VendorBill.id.desc())


def _data_quality(db: Session, company_id: int, start: datetime, end: datetime) -> TaxReportDataQuality:
    outward = _outward_query(db, company_id, start, end).all()
    inward = _inward_query(db, company_id, start, end).all()

    outward_missing = sum(1 for inv in outward if not _valid_gstin(inv.client_gstin))
    inward_missing = sum(1 for bill in inward if not _valid_gstin(bill.vendor_gstin))

    excluded_outward = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(OUTWARD_DRAFT_STATUSES),
            Invoice.issue_date.isnot(None),
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
        )
        .count()
    )
    excluded_inward = (
        db.query(VendorBill)
        .filter(
            VendorBill.company_id == company_id,
            VendorBill.status.in_(INWARD_DRAFT_STATUSES),
            VendorBill.bill_date >= start,
            VendorBill.bill_date <= end,
        )
        .count()
    )

    return TaxReportDataQuality(
        outward_missing_gstin=outward_missing,
        inward_missing_gstin=inward_missing,
        excluded_outward_drafts=excluded_outward,
        excluded_inward_drafts=excluded_inward,
    )


def _outward_register_row(inv: Invoice) -> TaxReportOutwardRegisterRow:
    customer = inv.client_name or inv.client_org
    return TaxReportOutwardRegisterRow(
        id=inv.id,
        invoice_number=inv.invoice_number,
        issue_date=inv.issue_date,
        customer_name=customer,
        customer_gstin=inv.client_gstin,
        taxable_value=_float(inv.subtotal),
        tax_amount=_float(inv.total_tax),
        grand_total=_float(inv.grand_total),
        status=inv.status,
        status_label=INVOICE_STATUS_LABELS.get(inv.status, inv.status),
        invoice_type=inv.invoice_type,
        is_credit_note=inv.invoice_type == "credit_note",
        tax_rate_summary=_tax_rate_summary(inv.line_items),
        missing_gstin=not _valid_gstin(inv.client_gstin),
        parent_invoice_id=inv.parent_invoice_id,
    )


def _inward_register_row(bill: VendorBill) -> TaxReportInwardRegisterRow:
    po_number = bill.purchase_order.po_number if bill.purchase_order else None
    return TaxReportInwardRegisterRow(
        id=bill.id,
        bill_number=bill.bill_number,
        supplier_invoice_number=bill.supplier_invoice_number,
        bill_date=bill.bill_date,
        vendor_name=bill.vendor_name,
        vendor_gstin=bill.vendor_gstin,
        taxable_value=_float(bill.subtotal),
        tax_amount=_float(bill.total_tax),
        grand_total=_float(bill.grand_total),
        status=bill.status,
        status_label=VENDOR_BILL_STATUS_LABELS.get(bill.status, bill.status),
        purchase_order_id=bill.purchase_order_id,
        po_number=po_number,
        tax_rate_summary=_tax_rate_summary(bill.line_items),
        missing_gstin=not _valid_gstin(bill.vendor_gstin),
    )


def _paginate_list(items: list, page: int, per_page: int):
    page = max(1, page)
    per_page = min(max(1, per_page), 200)
    total = len(items)
    start_idx = (page - 1) * per_page
    return items[start_idx : start_idx + per_page], total, page, per_page


@router.get("/periods", response_model=list[TaxReportPeriodOption])
def list_periods(_user: User = Depends(_require_tax_view)):
    return [TaxReportPeriodOption(key=k, label=PERIOD_LABELS[k]) for k in REPORT_PERIODS]


@router.get("/overview", response_model=TaxReportOverviewResponse)
def overview(
    period: str = Query(default="month"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(_require_tax_view),
):
    company = get_current_company(db, _user)
    start, end, label = _period_bounds(period, date_from, date_to, company.financial_year_start_month or 4)

    outward = _outward_query(db, company.id, start, end).all()
    inward = _inward_query(db, company.id, start, end).all()
    quality = _data_quality(db, company.id, start, end)

    return TaxReportOverviewResponse(
        period=period,
        period_label=label,
        date_from=start,
        date_to=end,
        company=_company_context(company),
        outward_taxable_value=round(sum(_float(i.subtotal) for i in outward), 2),
        outward_tax_collected=round(sum(_float(i.total_tax) for i in outward), 2),
        outward_document_count=len(outward),
        inward_taxable_value=round(sum(_float(b.subtotal) for b in inward), 2),
        inward_input_tax=round(sum(_float(b.total_tax) for b in inward), 2),
        inward_document_count=len(inward),
        missing_gstin_count=quality.outward_missing_gstin + quality.inward_missing_gstin,
        data_quality=quality,
    )


@router.get("/sales", response_model=TaxReportSalesResponse)
def sales_report(
    period: str = Query(default="month"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_sales_view),
):
    company = get_current_company(db, _user)
    start, end, label = _period_bounds(period, date_from, date_to, company.financial_year_start_month or 4)

    query = _outward_query(db, company.id, start, end, search)
    all_invoices = query.all()
    register_rows, total, page, per_page = _paginate_list(all_invoices, page, per_page)

    b2b = sum(1 for inv in all_invoices if _valid_gstin(inv.client_gstin))
    b2c = len(all_invoices) - b2b

    return TaxReportSalesResponse(
        period=period,
        period_label=label,
        date_from=start,
        date_to=end,
        company=_company_context(company),
        taxable_value=round(sum(_float(i.subtotal) for i in all_invoices), 2),
        tax_collected=round(sum(_float(i.total_tax) for i in all_invoices), 2),
        gross_total=round(sum(_float(i.grand_total) for i in all_invoices), 2),
        document_count=len(all_invoices),
        b2b_count=b2b,
        b2c_count=b2c,
        rate_breakdown=_aggregate_rate_breakdown(all_invoices, "line_items"),
        register=[_outward_register_row(inv) for inv in register_rows],
        register_total=total,
        register_page=page,
        register_per_page=per_page,
        data_quality=_data_quality(db, company.id, start, end),
    )


@router.get("/purchase", response_model=TaxReportPurchaseResponse)
def purchase_report(
    period: str = Query(default="month"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_purchase_view),
):
    company = get_current_company(db, _user)
    start, end, label = _period_bounds(period, date_from, date_to, company.financial_year_start_month or 4)

    query = _inward_query(db, company.id, start, end, search)
    all_bills = query.all()
    register_rows, total, page, per_page = _paginate_list(all_bills, page, per_page)

    vendor_map: dict[str, TaxReportVendorSummaryRow] = {}
    for bill in all_bills:
        key = bill.vendor_name or "Unknown"
        if key not in vendor_map:
            vendor_map[key] = TaxReportVendorSummaryRow(
                vendor_name=key,
                bill_count=0,
                taxable_value=0.0,
                input_tax=0.0,
            )
        vendor_map[key].bill_count += 1
        vendor_map[key].taxable_value = round(vendor_map[key].taxable_value + _float(bill.subtotal), 2)
        vendor_map[key].input_tax = round(vendor_map[key].input_tax + _float(bill.total_tax), 2)

    vendor_summary = sorted(vendor_map.values(), key=lambda v: v.input_tax, reverse=True)[:10]

    return TaxReportPurchaseResponse(
        period=period,
        period_label=label,
        date_from=start,
        date_to=end,
        company=_company_context(company),
        taxable_value=round(sum(_float(b.subtotal) for b in all_bills), 2),
        input_tax=round(sum(_float(b.total_tax) for b in all_bills), 2),
        gross_total=round(sum(_float(b.grand_total) for b in all_bills), 2),
        document_count=len(all_bills),
        vendors_with_gstin=sum(1 for b in all_bills if _valid_gstin(b.vendor_gstin)),
        rate_breakdown=_aggregate_rate_breakdown(all_bills, "line_items"),
        vendor_summary=vendor_summary,
        register=[_inward_register_row(bill) for bill in register_rows],
        register_total=total,
        register_page=page,
        register_per_page=per_page,
        data_quality=_data_quality(db, company.id, start, end),
    )


@router.get("/summary", response_model=TaxReportSummaryResponse)
def summary_report(
    period: str = Query(default="month"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(_require_summary_view),
):
    company = get_current_company(db, _user)
    start, end, label = _period_bounds(period, date_from, date_to, company.financial_year_start_month or 4)

    outward = _outward_query(db, company.id, start, end).all()
    inward = _inward_query(db, company.id, start, end).all()

    outward_tax = round(sum(_float(i.total_tax) for i in outward), 2)
    inward_tax = round(sum(_float(b.total_tax) for b in inward), 2)

    outward_rates = _aggregate_rate_breakdown(outward, "line_items")
    inward_rates = _aggregate_rate_breakdown(inward, "line_items")

    return TaxReportSummaryResponse(
        period=period,
        period_label=label,
        date_from=start,
        date_to=end,
        company=_company_context(company),
        outward_taxable_value=round(sum(_float(i.subtotal) for i in outward), 2),
        outward_tax_collected=outward_tax,
        outward_document_count=len(outward),
        inward_taxable_value=round(sum(_float(b.subtotal) for b in inward), 2),
        inward_input_tax=inward_tax,
        inward_document_count=len(inward),
        informational_net_tax=round(outward_tax - inward_tax, 2),
        rate_breakdown=_merge_rate_breakdown(outward_rates, inward_rates),
        data_quality=_data_quality(db, company.id, start, end),
    )


@router.post("/export-log")
def export_log(
    payload: TaxReportExportLogRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_require_export),
):
    details = f"{payload.report_type} export — {payload.period_label or payload.period} ({payload.row_count} rows)"
    log_activity(
        db,
        "tax_report_exported",
        user_id=user.id,
        email=user.email,
        details=details,
        ip_address=get_client_ip(request),
    )
    return {"ok": True}
