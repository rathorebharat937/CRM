from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_current_user, get_db
from customer_ledger_config import (
    CREDIT_INVOICE_TYPES,
    ENTRY_TYPE_CREDIT_NOTE,
    ENTRY_TYPE_DEBIT_NOTE,
    ENTRY_TYPE_INVOICE,
    ENTRY_TYPE_LABELS,
    ENTRY_TYPE_PAYMENT,
    ENTRY_TYPE_WRITE_OFF,
    EXCLUDED_INVOICE_TYPES,
    LEDGER_INVOICE_STATUSES,
    OUTSTANDING_STATUSES,
    PERIOD_LABELS,
    REPORT_PERIODS,
)
from invoice_config import INVOICE_STATUS_LABELS
from models import Company, Contact, Invoice, InvoicePayment, User
from permissions import role_has_permission
from schemas import (
    CustomerLedgerContactHeader,
    CustomerLedgerContactSummaryResponse,
    CustomerLedgerEntryRow,
    CustomerLedgerExportLogRequest,
    CustomerLedgerIndexKpis,
    CustomerLedgerIndexResponse,
    CustomerLedgerIndexRow,
    CustomerLedgerOpenInvoiceRow,
    CustomerLedgerPeriodOption,
    CustomerLedgerStatementResponse,
    CustomerLedgerStatementSummary,
    CustomerLedgerUnassignedGroup,
    CustomerLedgerUnassignedInvoiceRow,
    CustomerLedgerUnassignedResponse,
    PaymentAgingBucket,
)

router = APIRouter(prefix="/customer-ledger", tags=["customer-ledger"])


def _float(v) -> float:
    return 0.0 if v is None else float(v)




def _has_any_permission(db: Session, role: str, codes: tuple[str, ...]) -> bool:
    return any(role_has_permission(db, role, code) for code in codes)


def _require_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(
        db,
        user.role,
        ("customer_ledger.view", "invoices.view", "payments.view"),
    ):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_export(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(
        db,
        user.role,
        ("customer_ledger.export", "reports.export", "invoices.view"),
    ):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


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
) -> tuple[datetime | None, datetime | None, str]:
    now = datetime.now(timezone.utc)

    if period == "all_time":
        return None, now, PERIOD_LABELS[period]

    if period == "custom":
        if not date_from or not date_to:
            raise HTTPException(status_code=400, detail="Custom period requires date_from and date_to")
        start = date_from if date_from.tzinfo else date_from.replace(tzinfo=timezone.utc)
        end = date_to if date_to.tzinfo else date_to.replace(tzinfo=timezone.utc)
        if end < start:
            raise HTTPException(status_code=400, detail="date_to must be on or after date_from")
        return start, end, PERIOD_LABELS.get(period, period)

    if period == "month":
        return _month_start(now.year, now.month), now, PERIOD_LABELS[period]

    if period == "last_month":
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
        return _month_start(year, month), _month_end(year, month), PERIOD_LABELS[period]

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
        return _month_start(q_start_year, q_start_month), now, PERIOD_LABELS[period]

    if period == "financial_year":
        fy_year = _fy_start_year(now, fy_start_month)
        return _month_start(fy_year, fy_start_month), now, f"FY {fy_year}-{str(fy_year + 1)[-2:]}"

    if period == "last_financial_year":
        current_fy_year = _fy_start_year(now, fy_start_month)
        prev_fy_year = current_fy_year - 1
        start = _month_start(prev_fy_year, fy_start_month)
        end_month = fy_start_month - 1 if fy_start_month > 1 else 12
        end_year = prev_fy_year if fy_start_month > 1 else prev_fy_year + 1
        return start, _month_end(end_year, end_month), f"FY {prev_fy_year}-{str(prev_fy_year + 1)[-2:]}"

    raise HTTPException(status_code=400, detail=f"Period must be one of: {', '.join(REPORT_PERIODS)}")


def _invoice_effective_date(inv: Invoice) -> datetime:
    if inv.issue_date:
        return inv.issue_date if inv.issue_date.tzinfo else inv.issue_date.replace(tzinfo=timezone.utc)
    if inv.issued_at:
        return inv.issued_at if inv.issued_at.tzinfo else inv.issued_at.replace(tzinfo=timezone.utc)
    created = inv.created_at or datetime.now(timezone.utc)
    return created if created.tzinfo else created.replace(tzinfo=timezone.utc)


def _write_off_date(inv: Invoice) -> datetime:
    if inv.last_status_change_at:
        dt = inv.last_status_change_at
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if inv.closed_at:
        dt = inv.closed_at
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return _invoice_effective_date(inv)


def _is_overdue(inv: Invoice, now: datetime) -> bool:
    if not inv.due_date or inv.status not in OUTSTANDING_STATUSES or _float(inv.outstanding_amount) <= 0:
        return False
    due = inv.due_date if inv.due_date.tzinfo else inv.due_date.replace(tzinfo=timezone.utc)
    return due < now


def _ledger_invoices_query(db: Session, company_id: int, contact_id: int | None = None, unassigned: bool = False):
    q = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(LEDGER_INVOICE_STATUSES),
            Invoice.invoice_type.notin_(list(EXCLUDED_INVOICE_TYPES)),
        )
    )
    if unassigned:
        q = q.filter(Invoice.contact_id.is_(None))
    elif contact_id is not None:
        q = q.filter(Invoice.contact_id == contact_id)
    else:
        q = q.filter(Invoice.contact_id.isnot(None))
    return q


def _invoice_entry_type(inv: Invoice) -> str:
    if inv.invoice_type in CREDIT_INVOICE_TYPES:
        return ENTRY_TYPE_CREDIT_NOTE
    if inv.invoice_type == "debit_note":
        return ENTRY_TYPE_DEBIT_NOTE
    return ENTRY_TYPE_INVOICE


def _invoice_debit_credit(inv: Invoice) -> tuple[float, float]:
    gt = _float(inv.grand_total)
    if inv.invoice_type in CREDIT_INVOICE_TYPES or gt < 0:
        return 0.0, round(abs(gt), 2)
    return round(abs(gt), 2), 0.0


def _build_entries(invoices: list[Invoice]) -> list[dict]:
    raw: list[dict] = []
    for inv in invoices:
        debit, credit = _invoice_debit_credit(inv)
        entry_type = _invoice_entry_type(inv)
        raw.append(
            {
                "entry_key": f"inv-{inv.id}",
                "entry_type": entry_type,
                "entry_type_label": ENTRY_TYPE_LABELS[entry_type],
                "effective_date": _invoice_effective_date(inv),
                "reference": inv.invoice_number,
                "description": inv.title,
                "debit_amount": debit,
                "credit_amount": credit,
                "invoice_id": inv.id,
                "payment_id": None,
                "status": inv.status,
                "status_label": INVOICE_STATUS_LABELS.get(inv.status, inv.status),
                "is_overdue": False,
                "sort_order": 0,
            }
        )
        for payment in inv.payments or []:
            pdate = payment.payment_date
            if pdate and pdate.tzinfo is None:
                pdate = pdate.replace(tzinfo=timezone.utc)
            raw.append(
                {
                    "entry_key": f"pay-{payment.id}",
                    "entry_type": ENTRY_TYPE_PAYMENT,
                    "entry_type_label": ENTRY_TYPE_LABELS[ENTRY_TYPE_PAYMENT],
                    "effective_date": pdate or _invoice_effective_date(inv),
                    "reference": payment.reference or inv.invoice_number,
                    "description": payment.note or f"Payment on {inv.invoice_number or inv.title}",
                    "debit_amount": 0.0,
                    "credit_amount": round(_float(payment.amount), 2),
                    "invoice_id": inv.id,
                    "payment_id": payment.id,
                    "status": inv.status,
                    "status_label": INVOICE_STATUS_LABELS.get(inv.status, inv.status),
                    "is_overdue": False,
                    "sort_order": 1,
                }
            )
        if inv.status == "written_off" and _float(inv.write_off_amount) > 0:
            raw.append(
                {
                    "entry_key": f"wo-{inv.id}",
                    "entry_type": ENTRY_TYPE_WRITE_OFF,
                    "entry_type_label": ENTRY_TYPE_LABELS[ENTRY_TYPE_WRITE_OFF],
                    "effective_date": _write_off_date(inv),
                    "reference": inv.invoice_number,
                    "description": inv.adjustment_reason or f"Write-off on {inv.invoice_number or inv.title}",
                    "debit_amount": 0.0,
                    "credit_amount": round(_float(inv.write_off_amount), 2),
                    "invoice_id": inv.id,
                    "payment_id": None,
                    "status": inv.status,
                    "status_label": INVOICE_STATUS_LABELS.get(inv.status, inv.status),
                    "is_overdue": False,
                    "sort_order": 2,
                }
            )
    raw.sort(key=lambda e: (e["effective_date"], e["sort_order"], e["entry_key"]))
    return raw


def _running_balance_entries(raw: list[dict], opening: float = 0.0) -> list[CustomerLedgerEntryRow]:
    balance = round(opening, 2)
    rows: list[CustomerLedgerEntryRow] = []
    for item in raw:
        balance = round(balance + item["debit_amount"] - item["credit_amount"], 2)
        rows.append(
            CustomerLedgerEntryRow(
                entry_key=item["entry_key"],
                entry_type=item["entry_type"],
                entry_type_label=item["entry_type_label"],
                effective_date=item["effective_date"],
                reference=item["reference"],
                description=item["description"],
                debit_amount=item["debit_amount"],
                credit_amount=item["credit_amount"],
                running_balance=balance,
                invoice_id=item["invoice_id"],
                payment_id=item["payment_id"],
                status=item["status"],
                status_label=item["status_label"],
                is_overdue=item["is_overdue"],
            )
        )
    return rows


def _opening_balance(all_raw: list[dict], period_start: datetime | None) -> float:
    if period_start is None:
        return 0.0
    total = 0.0
    for item in all_raw:
        if item["effective_date"] < period_start:
            total += item["debit_amount"] - item["credit_amount"]
    return round(total, 2)


def _filter_period(raw: list[dict], period_start: datetime | None, period_end: datetime | None) -> list[dict]:
    if period_start is None and period_end is None:
        return raw
    filtered = []
    for item in raw:
        dt = item["effective_date"]
        if period_start and dt < period_start:
            continue
        if period_end and dt > period_end:
            continue
        filtered.append(item)
    return filtered


def _contact_metrics(invoices: list[Invoice], now: datetime) -> dict:
    total_billed = round(sum(_float(i.grand_total) for i in invoices), 2)
    total_collected = round(
        sum(_float(p.amount) for i in invoices for p in (i.payments or [])),
        2,
    )
    outstanding = round(
        sum(
            _float(i.outstanding_amount)
            for i in invoices
            if i.status in OUTSTANDING_STATUSES and _float(i.outstanding_amount) > 0
        ),
        2,
    )
    overdue = round(
        sum(
            _float(i.outstanding_amount)
            for i in invoices
            if _is_overdue(i, now)
        ),
        2,
    )
    open_count = sum(
        1 for i in invoices if i.status in OUTSTANDING_STATUSES and _float(i.outstanding_amount) > 0
    )
    dates: list[datetime] = []
    for inv in invoices:
        dates.append(_invoice_effective_date(inv))
        for p in inv.payments or []:
            if p.payment_date:
                dates.append(p.payment_date if p.payment_date.tzinfo else p.payment_date.replace(tzinfo=timezone.utc))
        if inv.status == "written_off":
            dates.append(_write_off_date(inv))
    last_activity = max(dates) if dates else None
    return {
        "total_billed": total_billed,
        "total_collected": total_collected,
        "outstanding": outstanding,
        "overdue_outstanding": overdue,
        "open_invoice_count": open_count,
        "last_activity_date": last_activity,
    }


def _aging_buckets(invoices: list[Invoice], now: datetime) -> list[PaymentAgingBucket]:
    open_invoices = [
        i
        for i in invoices
        if i.status in OUTSTANDING_STATUSES and _float(i.outstanding_amount) > 0
    ]
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
        for inv in open_invoices:
            if not inv.issue_date:
                continue
            issue = inv.issue_date if inv.issue_date.tzinfo else inv.issue_date.replace(tzinfo=timezone.utc)
            age_days = (now - issue).days
            if min_days <= age_days <= max_days:
                amount += _float(inv.outstanding_amount)
                count += 1
        aging.append(PaymentAgingBucket(label=label, count=count, amount=round(amount, 2)))
    return aging


def _open_invoice_rows(invoices: list[Invoice], now: datetime) -> list[CustomerLedgerOpenInvoiceRow]:
    rows = []
    for inv in invoices:
        if inv.status not in OUTSTANDING_STATUSES or _float(inv.outstanding_amount) <= 0:
            continue
        rows.append(
            CustomerLedgerOpenInvoiceRow(
                id=inv.id,
                invoice_number=inv.invoice_number,
                title=inv.title,
                invoice_type=inv.invoice_type,
                issue_date=inv.issue_date,
                due_date=inv.due_date,
                grand_total=_float(inv.grand_total),
                amount_paid=_float(inv.amount_paid),
                outstanding_amount=_float(inv.outstanding_amount),
                status=inv.status,
                status_label=INVOICE_STATUS_LABELS.get(inv.status, inv.status),
                is_overdue=_is_overdue(inv, now),
            )
        )
    rows.sort(key=lambda r: (r.due_date is None, r.due_date or datetime.min.replace(tzinfo=timezone.utc)))
    return rows


def _contact_header(contact: Contact, company: Company) -> CustomerLedgerContactHeader:
    parts = [contact.address_line1, contact.address_line2, contact.city, contact.state, contact.pincode]
    address = ", ".join(p for p in parts if p)
    gstin = contact.gstin.strip() if contact.gstin else None
    return CustomerLedgerContactHeader(
        contact_id=contact.id,
        name=contact.name,
        organization_name=contact.organization_name,
        gstin=gstin,
        pan=contact.pan,
        email=contact.email,
        phone=contact.phone,
        contact_type=contact.contact_type,
        billing_address=address or None,
        currency=company.currency or "INR",
        is_vendor=contact.contact_type == "Vendor",
        missing_gstin=not bool(gstin),
    )


def _paginate(items: list, page: int, per_page: int):
    page = max(1, page)
    per_page = min(max(1, per_page), 200)
    total = len(items)
    start = (page - 1) * per_page
    return items[start : start + per_page], total, page, per_page


@router.get("/periods", response_model=list[CustomerLedgerPeriodOption])
def list_periods(_user: User = Depends(_require_view)):
    return [CustomerLedgerPeriodOption(key=k, label=PERIOD_LABELS[k]) for k in REPORT_PERIODS]


@router.get("", response_model=CustomerLedgerIndexResponse)
def ledger_index(
    search: str | None = None,
    outstanding_only: bool = False,
    overdue_only: bool = False,
    sort: str = Query(default="outstanding", pattern="^(outstanding|name|activity)$"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    now = datetime.now(timezone.utc)

    invoices = _ledger_invoices_query(db, company.id).all()
    unassigned_invoices = _ledger_invoices_query(db, company.id, unassigned=True).all()
    unassigned_outstanding = round(
        sum(
            _float(i.outstanding_amount)
            for i in unassigned_invoices
            if i.status in OUTSTANDING_STATUSES and _float(i.outstanding_amount) > 0
        ),
        2,
    )

    by_contact: dict[int, list[Invoice]] = defaultdict(list)
    for inv in invoices:
        if inv.contact_id:
            by_contact[inv.contact_id].append(inv)

    contact_ids = list(by_contact.keys())
    contacts = {
        c.id: c
        for c in db.query(Contact).filter(Contact.company_id == company.id, Contact.id.in_(contact_ids)).all()
    } if contact_ids else {}

    rows: list[CustomerLedgerIndexRow] = []
    total_outstanding = 0.0
    total_overdue = 0.0
    customers_with_balance = 0
    month_start = _month_start(now.year, now.month)
    collected_this_month = 0.0

    for contact_id, invs in by_contact.items():
        contact = contacts.get(contact_id)
        if not contact:
            continue
        metrics = _contact_metrics(invs, now)
        total_outstanding += metrics["outstanding"]
        total_overdue += metrics["overdue_outstanding"]
        if metrics["outstanding"] > 0:
            customers_with_balance += 1
        for inv in invs:
            for p in inv.payments or []:
                pdate = p.payment_date
                if pdate:
                    if pdate.tzinfo is None:
                        pdate = pdate.replace(tzinfo=timezone.utc)
                    if pdate >= month_start:
                        collected_this_month += _float(p.amount)

        if outstanding_only and metrics["outstanding"] <= 0:
            continue
        if overdue_only and metrics["overdue_outstanding"] <= 0:
            continue
        if search:
            term = search.strip().lower()
            haystack = " ".join(
                filter(
                    None,
                    [
                        contact.name,
                        contact.organization_name,
                        contact.gstin,
                        contact.email,
                        contact.phone,
                    ],
                )
            ).lower()
            if term not in haystack:
                continue

        rows.append(
            CustomerLedgerIndexRow(
                contact_id=contact.id,
                name=contact.name,
                organization_name=contact.organization_name,
                gstin=contact.gstin,
                email=contact.email,
                phone=contact.phone,
                currency=company.currency or "INR",
                total_billed=metrics["total_billed"],
                total_collected=metrics["total_collected"],
                outstanding=metrics["outstanding"],
                overdue_outstanding=metrics["overdue_outstanding"],
                last_activity_date=metrics["last_activity_date"],
                open_invoice_count=metrics["open_invoice_count"],
            )
        )

    if sort == "name":
        rows.sort(key=lambda r: r.name.lower())
    elif sort == "activity":
        rows.sort(key=lambda r: r.last_activity_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    else:
        rows.sort(key=lambda r: r.outstanding, reverse=True)

    page_rows, total, page, per_page = _paginate(rows, page, per_page)

    return CustomerLedgerIndexResponse(
        kpis=CustomerLedgerIndexKpis(
            total_outstanding=round(total_outstanding, 2),
            overdue_outstanding=round(total_overdue, 2),
            customers_with_balance=customers_with_balance,
            collected_this_month=round(collected_this_month, 2),
            unassigned_outstanding=unassigned_outstanding,
        ),
        items=page_rows,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/unassigned", response_model=CustomerLedgerUnassignedResponse)
def unassigned_receivables(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    now = datetime.now(timezone.utc)
    invoices = _ledger_invoices_query(db, company.id, unassigned=True).order_by(Invoice.issue_date.desc()).all()

    total_outstanding = round(
        sum(
            _float(i.outstanding_amount)
            for i in invoices
            if i.status in OUTSTANDING_STATUSES and _float(i.outstanding_amount) > 0
        ),
        2,
    )

    groups_map: dict[str, CustomerLedgerUnassignedGroup] = {}
    for inv in invoices:
        key = (inv.client_org or inv.client_name or "Unknown").strip().lower()
        if key not in groups_map:
            groups_map[key] = CustomerLedgerUnassignedGroup(
                group_key=key,
                client_name=inv.client_name,
                client_org=inv.client_org,
                invoice_count=0,
                total_billed=0.0,
                outstanding=0.0,
            )
        g = groups_map[key]
        g.invoice_count += 1
        g.total_billed = round(g.total_billed + _float(inv.grand_total), 2)
        if inv.status in OUTSTANDING_STATUSES:
            g.outstanding = round(g.outstanding + _float(inv.outstanding_amount), 2)

    invoice_rows = [
        CustomerLedgerUnassignedInvoiceRow(
            id=inv.id,
            invoice_number=inv.invoice_number,
            title=inv.title,
            client_name=inv.client_name,
            client_org=inv.client_org,
            issue_date=inv.issue_date,
            due_date=inv.due_date,
            grand_total=_float(inv.grand_total),
            outstanding_amount=_float(inv.outstanding_amount),
            status=inv.status,
            status_label=INVOICE_STATUS_LABELS.get(inv.status, inv.status),
            is_overdue=_is_overdue(inv, now),
        )
        for inv in invoices
    ]

    page_rows, total, page, per_page = _paginate(invoice_rows, page, per_page)
    groups = sorted(groups_map.values(), key=lambda g: g.outstanding, reverse=True)

    return CustomerLedgerUnassignedResponse(
        total_outstanding=total_outstanding,
        invoice_count=len(invoices),
        groups=groups,
        invoices=page_rows,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/contacts/{contact_id}/summary", response_model=CustomerLedgerContactSummaryResponse)
def contact_summary(
    contact_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.company_id == company.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    now = datetime.now(timezone.utc)
    invoices = _ledger_invoices_query(db, company.id, contact_id=contact_id).all()
    metrics = _contact_metrics(invoices, now)

    last_payment = None
    for inv in invoices:
        for p in inv.payments or []:
            pdate = p.payment_date
            if pdate:
                if pdate.tzinfo is None:
                    pdate = pdate.replace(tzinfo=timezone.utc)
                if last_payment is None or pdate > last_payment:
                    last_payment = pdate

    return CustomerLedgerContactSummaryResponse(
        contact_id=contact.id,
        outstanding=metrics["outstanding"],
        overdue_outstanding=metrics["overdue_outstanding"],
        open_invoice_count=metrics["open_invoice_count"],
        last_payment_date=last_payment,
        total_collected=metrics["total_collected"],
    )


@router.get("/contacts/{contact_id}/statement", response_model=CustomerLedgerStatementResponse)
def customer_statement(
    contact_id: int,
    period: str = Query(default="all_time"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.company_id == company.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    now = datetime.now(timezone.utc)
    period_start, period_end, label = _period_bounds(
        period, date_from, date_to, company.financial_year_start_month or 4
    )

    invoices = _ledger_invoices_query(db, company.id, contact_id=contact_id).all()
    all_raw = _build_entries(invoices)
    opening = _opening_balance(all_raw, period_start)
    period_raw = _filter_period(all_raw, period_start, period_end)
    period_entries = _running_balance_entries(period_raw, opening)

    page_entries, entries_total, page, per_page = _paginate(period_entries, page, per_page)

    period_debits = round(sum(e["debit_amount"] for e in period_raw), 2)
    period_credits = round(sum(e["credit_amount"] for e in period_raw), 2)
    closing = round(opening + period_debits - period_credits, 2)
    metrics = _contact_metrics(invoices, now)

    return CustomerLedgerStatementResponse(
        period=period,
        period_label=label,
        date_from=period_start,
        date_to=period_end,
        contact=_contact_header(contact, company),
        summary=CustomerLedgerStatementSummary(
            opening_balance=opening,
            period_debits=period_debits,
            period_credits=period_credits,
            closing_balance=closing,
            current_outstanding=metrics["outstanding"],
            overdue_outstanding=metrics["overdue_outstanding"],
        ),
        entries=page_entries,
        entries_total=entries_total,
        entries_page=page,
        entries_per_page=per_page,
        open_invoices=_open_invoice_rows(invoices, now),
        aging_buckets=_aging_buckets(invoices, now),
    )


@router.post("/export-log")
def export_log(
    payload: CustomerLedgerExportLogRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_require_export),
):
    details = f"Customer ledger export — contact {payload.contact_id} · {payload.period_label or payload.period} ({payload.row_count} rows)"
    log_activity(
        db,
        "customer_ledger_exported",
        user_id=user.id,
        email=user.email,
        details=details,
        ip_address=get_client_ip(request),
    )
    return {"ok": True}
