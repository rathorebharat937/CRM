from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_current_user, get_db
from models import Company, Contact, User, VendorBill, VendorBillPayment
from permissions import role_has_permission
from schemas import (
    PaymentAgingBucket,
    VendorLedgerContactHeader,
    VendorLedgerContactSummaryResponse,
    VendorLedgerEntryRow,
    VendorLedgerExportLogRequest,
    VendorLedgerIndexKpis,
    VendorLedgerIndexResponse,
    VendorLedgerIndexRow,
    VendorLedgerOpenBillRow,
    VendorLedgerPeriodOption,
    VendorLedgerStatementResponse,
    VendorLedgerStatementSummary,
    VendorLedgerUnassignedBillRow,
    VendorLedgerUnassignedGroup,
    VendorLedgerUnassignedResponse,
)
from vendor_bills_config import VENDOR_BILL_STATUS_LABELS
from vendor_ledger_config import (
    ENTRY_TYPE_BILL,
    ENTRY_TYPE_LABELS,
    ENTRY_TYPE_PAYMENT,
    LEDGER_BILL_STATUSES,
    OUTSTANDING_STATUSES,
    PERIOD_LABELS,
    REPORT_PERIODS,
)

router = APIRouter(prefix="/vendor-ledger", tags=["vendor-ledger"])


def _float(v) -> float:
    return 0.0 if v is None else float(v)




def _has_any_permission(db: Session, role: str, codes: tuple[str, ...]) -> bool:
    return any(role_has_permission(db, role, code) for code in codes)


def _require_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(db, user.role, ("vendor_ledger.view", "vendor_bills.view")):
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def _require_export(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if _has_any_permission(
        db,
        user.role,
        ("vendor_ledger.export", "vendor_bills.export", "reports.export"),
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


def _bill_effective_date(bill: VendorBill) -> datetime:
    if bill.bill_date:
        return bill.bill_date if bill.bill_date.tzinfo else bill.bill_date.replace(tzinfo=timezone.utc)
    if bill.approved_at:
        dt = bill.approved_at
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    created = bill.created_at or datetime.now(timezone.utc)
    return created if created.tzinfo else created.replace(tzinfo=timezone.utc)


def _is_overdue(bill: VendorBill, now: datetime) -> bool:
    if not bill.due_date or bill.status not in OUTSTANDING_STATUSES or _float(bill.outstanding_amount) <= 0:
        return False
    due = bill.due_date if bill.due_date.tzinfo else bill.due_date.replace(tzinfo=timezone.utc)
    return due < now


def _ledger_bills_query(db: Session, company_id: int, contact_id: int | None = None, unassigned: bool = False):
    q = (
        db.query(VendorBill)
        .options(joinedload(VendorBill.payments), joinedload(VendorBill.purchase_order))
        .filter(
            VendorBill.company_id == company_id,
            VendorBill.status.in_(LEDGER_BILL_STATUSES),
        )
    )
    if unassigned:
        q = q.filter(VendorBill.contact_id.is_(None))
    elif contact_id is not None:
        q = q.filter(VendorBill.contact_id == contact_id)
    else:
        q = q.filter(VendorBill.contact_id.isnot(None))
    return q


def _po_number(bill: VendorBill) -> str | None:
    return bill.purchase_order.po_number if bill.purchase_order else None


def _build_entries(bills: list[VendorBill]) -> list[dict]:
    raw: list[dict] = []
    for bill in bills:
        po = _po_number(bill)
        ref = bill.bill_number or bill.supplier_invoice_number
        raw.append(
            {
                "entry_key": f"bill-{bill.id}",
                "entry_type": ENTRY_TYPE_BILL,
                "entry_type_label": ENTRY_TYPE_LABELS[ENTRY_TYPE_BILL],
                "effective_date": _bill_effective_date(bill),
                "reference": ref,
                "description": bill.title,
                "debit_amount": round(_float(bill.grand_total), 2),
                "credit_amount": 0.0,
                "bill_id": bill.id,
                "payment_id": None,
                "po_number": po,
                "status": bill.status,
                "status_label": VENDOR_BILL_STATUS_LABELS.get(bill.status, bill.status),
                "is_overdue": False,
                "sort_order": 0,
            }
        )
        for payment in bill.payments or []:
            pdate = payment.payment_date
            if pdate and pdate.tzinfo is None:
                pdate = pdate.replace(tzinfo=timezone.utc)
            raw.append(
                {
                    "entry_key": f"pay-{payment.id}",
                    "entry_type": ENTRY_TYPE_PAYMENT,
                    "entry_type_label": ENTRY_TYPE_LABELS[ENTRY_TYPE_PAYMENT],
                    "effective_date": pdate or _bill_effective_date(bill),
                    "reference": payment.reference or bill.bill_number,
                    "description": payment.note or f"Payment on {bill.bill_number or bill.title}",
                    "debit_amount": 0.0,
                    "credit_amount": round(_float(payment.amount), 2),
                    "bill_id": bill.id,
                    "payment_id": payment.id,
                    "po_number": po,
                    "status": bill.status,
                    "status_label": VENDOR_BILL_STATUS_LABELS.get(bill.status, bill.status),
                    "is_overdue": False,
                    "sort_order": 1,
                }
            )
    raw.sort(key=lambda e: (e["effective_date"], e["sort_order"], e["entry_key"]))
    return raw


def _running_balance_entries(raw: list[dict], opening: float = 0.0) -> list[VendorLedgerEntryRow]:
    balance = round(opening, 2)
    rows: list[VendorLedgerEntryRow] = []
    for item in raw:
        balance = round(balance + item["debit_amount"] - item["credit_amount"], 2)
        rows.append(
            VendorLedgerEntryRow(
                entry_key=item["entry_key"],
                entry_type=item["entry_type"],
                entry_type_label=item["entry_type_label"],
                effective_date=item["effective_date"],
                reference=item["reference"],
                description=item["description"],
                debit_amount=item["debit_amount"],
                credit_amount=item["credit_amount"],
                running_balance=balance,
                bill_id=item["bill_id"],
                payment_id=item["payment_id"],
                po_number=item["po_number"],
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


def _vendor_metrics(bills: list[VendorBill], now: datetime) -> dict:
    total_billed = round(sum(_float(b.grand_total) for b in bills), 2)
    total_paid = round(sum(_float(p.amount) for b in bills for p in (b.payments or [])), 2)
    outstanding = round(
        sum(
            _float(b.outstanding_amount)
            for b in bills
            if b.status in OUTSTANDING_STATUSES and _float(b.outstanding_amount) > 0
        ),
        2,
    )
    overdue = round(sum(_float(b.outstanding_amount) for b in bills if _is_overdue(b, now)), 2)
    open_count = sum(
        1 for b in bills if b.status in OUTSTANDING_STATUSES and _float(b.outstanding_amount) > 0
    )
    dates: list[datetime] = []
    for bill in bills:
        dates.append(_bill_effective_date(bill))
        if bill.approved_at:
            dt = bill.approved_at
            dates.append(dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
        for p in bill.payments or []:
            if p.payment_date:
                dates.append(p.payment_date if p.payment_date.tzinfo else p.payment_date.replace(tzinfo=timezone.utc))
    last_activity = max(dates) if dates else None
    return {
        "total_billed": total_billed,
        "total_paid": total_paid,
        "outstanding": outstanding,
        "overdue_outstanding": overdue,
        "open_bill_count": open_count,
        "last_activity_date": last_activity,
    }


def _aging_buckets(bills: list[VendorBill], now: datetime) -> list[PaymentAgingBucket]:
    open_bills = [
        b for b in bills if b.status in OUTSTANDING_STATUSES and _float(b.outstanding_amount) > 0
    ]
    bucket_defs = [
        ("Current", "current"),
        ("1-30 days", "1_30"),
        ("31-60 days", "31_60"),
        ("61-90 days", "61_90"),
        ("90+ days", "90_plus"),
    ]
    amounts = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}
    counts = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}

    for bill in open_bills:
        out = _float(bill.outstanding_amount)
        if not bill.due_date:
            amounts["current"] += out
            counts["current"] += 1
            continue
        due = bill.due_date if bill.due_date.tzinfo else bill.due_date.replace(tzinfo=timezone.utc)
        days = (now - due).days
        if days <= 0:
            key = "current"
        elif days <= 30:
            key = "1_30"
        elif days <= 60:
            key = "31_60"
        elif days <= 90:
            key = "61_90"
        else:
            key = "90_plus"
        amounts[key] += out
        counts[key] += 1

    return [
        PaymentAgingBucket(label=label, count=counts[key], amount=round(amounts[key], 2))
        for label, key in bucket_defs
    ]


def _open_bill_rows(bills: list[VendorBill], now: datetime) -> list[VendorLedgerOpenBillRow]:
    rows = []
    for bill in bills:
        if bill.status not in OUTSTANDING_STATUSES or _float(bill.outstanding_amount) <= 0:
            continue
        rows.append(
            VendorLedgerOpenBillRow(
                id=bill.id,
                bill_number=bill.bill_number,
                supplier_invoice_number=bill.supplier_invoice_number,
                title=bill.title,
                bill_date=bill.bill_date,
                due_date=bill.due_date,
                grand_total=_float(bill.grand_total),
                amount_paid=_float(bill.amount_paid),
                outstanding_amount=_float(bill.outstanding_amount),
                status=bill.status,
                status_label=VENDOR_BILL_STATUS_LABELS.get(bill.status, bill.status),
                purchase_order_id=bill.purchase_order_id,
                po_number=_po_number(bill),
                is_overdue=_is_overdue(bill, now),
            )
        )
    rows.sort(key=lambda r: (r.due_date is None, r.due_date or datetime.min.replace(tzinfo=timezone.utc)))
    return rows


def _contact_header(contact: Contact, company: Company) -> VendorLedgerContactHeader:
    parts = [contact.address_line1, contact.address_line2, contact.city, contact.state, contact.pincode]
    address = ", ".join(p for p in parts if p)
    gstin = contact.gstin.strip() if contact.gstin else None
    return VendorLedgerContactHeader(
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
        is_customer=contact.contact_type == "Customer",
        missing_gstin=not bool(gstin),
    )


def _paginate(items: list, page: int, per_page: int):
    page = max(1, page)
    per_page = min(max(1, per_page), 200)
    total = len(items)
    start = (page - 1) * per_page
    return items[start : start + per_page], total, page, per_page


@router.get("/periods", response_model=list[VendorLedgerPeriodOption])
def list_periods(_user: User = Depends(_require_view)):
    return [VendorLedgerPeriodOption(key=k, label=PERIOD_LABELS[k]) for k in REPORT_PERIODS]


@router.get("", response_model=VendorLedgerIndexResponse)
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
    month_start = _month_start(now.year, now.month)

    bills = _ledger_bills_query(db, company.id).all()
    unassigned_bills = _ledger_bills_query(db, company.id, unassigned=True).all()
    unassigned_outstanding = round(
        sum(
            _float(b.outstanding_amount)
            for b in unassigned_bills
            if b.status in OUTSTANDING_STATUSES and _float(b.outstanding_amount) > 0
        ),
        2,
    )

    by_contact: dict[int, list[VendorBill]] = defaultdict(list)
    for bill in bills:
        if bill.contact_id:
            by_contact[bill.contact_id].append(bill)

    contact_ids = list(by_contact.keys())
    contacts = {
        c.id: c
        for c in db.query(Contact).filter(Contact.company_id == company.id, Contact.id.in_(contact_ids)).all()
    } if contact_ids else {}

    rows: list[VendorLedgerIndexRow] = []
    total_outstanding = 0.0
    total_overdue = 0.0
    vendors_with_balance = 0
    paid_this_month = 0.0

    for contact_id, vendor_bills in by_contact.items():
        contact = contacts.get(contact_id)
        if not contact:
            continue
        metrics = _vendor_metrics(vendor_bills, now)
        total_outstanding += metrics["outstanding"]
        total_overdue += metrics["overdue_outstanding"]
        if metrics["outstanding"] > 0:
            vendors_with_balance += 1
        for bill in vendor_bills:
            for p in bill.payments or []:
                pdate = p.payment_date
                if pdate:
                    if pdate.tzinfo is None:
                        pdate = pdate.replace(tzinfo=timezone.utc)
                    if pdate >= month_start:
                        paid_this_month += _float(p.amount)

        if outstanding_only and metrics["outstanding"] <= 0:
            continue
        if overdue_only and metrics["overdue_outstanding"] <= 0:
            continue
        if search:
            term = search.strip().lower()
            haystack = " ".join(
                filter(
                    None,
                    [contact.name, contact.organization_name, contact.gstin, contact.email, contact.phone],
                )
            ).lower()
            if term not in haystack:
                continue

        rows.append(
            VendorLedgerIndexRow(
                contact_id=contact.id,
                name=contact.name,
                organization_name=contact.organization_name,
                gstin=contact.gstin,
                email=contact.email,
                phone=contact.phone,
                currency=company.currency or "INR",
                total_billed=metrics["total_billed"],
                total_paid=metrics["total_paid"],
                outstanding=metrics["outstanding"],
                overdue_outstanding=metrics["overdue_outstanding"],
                last_activity_date=metrics["last_activity_date"],
                open_bill_count=metrics["open_bill_count"],
            )
        )

    if sort == "name":
        rows.sort(key=lambda r: r.name.lower())
    elif sort == "activity":
        rows.sort(key=lambda r: r.last_activity_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    else:
        rows.sort(key=lambda r: r.outstanding, reverse=True)

    page_rows, total, page, per_page = _paginate(rows, page, per_page)

    return VendorLedgerIndexResponse(
        kpis=VendorLedgerIndexKpis(
            total_outstanding=round(total_outstanding, 2),
            overdue_outstanding=round(total_overdue, 2),
            vendors_with_balance=vendors_with_balance,
            paid_this_month=round(paid_this_month, 2),
            unassigned_outstanding=unassigned_outstanding,
        ),
        items=page_rows,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/unassigned", response_model=VendorLedgerUnassignedResponse)
def unassigned_payables(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_view),
):
    company = get_current_company(db, _user)
    now = datetime.now(timezone.utc)
    bills = _ledger_bills_query(db, company.id, unassigned=True).order_by(VendorBill.bill_date.desc()).all()

    total_outstanding = round(
        sum(
            _float(b.outstanding_amount)
            for b in bills
            if b.status in OUTSTANDING_STATUSES and _float(b.outstanding_amount) > 0
        ),
        2,
    )

    groups_map: dict[str, VendorLedgerUnassignedGroup] = {}
    for bill in bills:
        key = bill.vendor_name.strip().lower()
        if key not in groups_map:
            groups_map[key] = VendorLedgerUnassignedGroup(
                group_key=key,
                vendor_name=bill.vendor_name,
                bill_count=0,
                total_billed=0.0,
                outstanding=0.0,
            )
        g = groups_map[key]
        g.bill_count += 1
        g.total_billed = round(g.total_billed + _float(bill.grand_total), 2)
        if bill.status in OUTSTANDING_STATUSES:
            g.outstanding = round(g.outstanding + _float(bill.outstanding_amount), 2)

    bill_rows = [
        VendorLedgerUnassignedBillRow(
            id=bill.id,
            bill_number=bill.bill_number,
            supplier_invoice_number=bill.supplier_invoice_number,
            title=bill.title,
            vendor_name=bill.vendor_name,
            bill_date=bill.bill_date,
            due_date=bill.due_date,
            grand_total=_float(bill.grand_total),
            outstanding_amount=_float(bill.outstanding_amount),
            status=bill.status,
            status_label=VENDOR_BILL_STATUS_LABELS.get(bill.status, bill.status),
            is_overdue=_is_overdue(bill, now),
        )
        for bill in bills
    ]

    page_rows, total, page, per_page = _paginate(bill_rows, page, per_page)
    groups = sorted(groups_map.values(), key=lambda g: g.outstanding, reverse=True)

    return VendorLedgerUnassignedResponse(
        total_outstanding=total_outstanding,
        bill_count=len(bills),
        groups=groups,
        bills=page_rows,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/contacts/{contact_id}/summary", response_model=VendorLedgerContactSummaryResponse)
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
    bills = _ledger_bills_query(db, company.id, contact_id=contact_id).all()
    metrics = _vendor_metrics(bills, now)

    last_payment = None
    for bill in bills:
        for p in bill.payments or []:
            pdate = p.payment_date
            if pdate:
                if pdate.tzinfo is None:
                    pdate = pdate.replace(tzinfo=timezone.utc)
                if last_payment is None or pdate > last_payment:
                    last_payment = pdate

    return VendorLedgerContactSummaryResponse(
        contact_id=contact.id,
        outstanding=metrics["outstanding"],
        overdue_outstanding=metrics["overdue_outstanding"],
        open_bill_count=metrics["open_bill_count"],
        last_payment_date=last_payment,
        total_paid=metrics["total_paid"],
    )


@router.get("/contacts/{contact_id}/statement", response_model=VendorLedgerStatementResponse)
def vendor_statement(
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

    bills = _ledger_bills_query(db, company.id, contact_id=contact_id).all()
    all_raw = _build_entries(bills)
    opening = _opening_balance(all_raw, period_start)
    period_raw = _filter_period(all_raw, period_start, period_end)
    period_entries = _running_balance_entries(period_raw, opening)

    page_entries, entries_total, page, per_page = _paginate(period_entries, page, per_page)

    period_debits = round(sum(e["debit_amount"] for e in period_raw), 2)
    period_credits = round(sum(e["credit_amount"] for e in period_raw), 2)
    closing = round(opening + period_debits - period_credits, 2)
    metrics = _vendor_metrics(bills, now)

    return VendorLedgerStatementResponse(
        period=period,
        period_label=label,
        date_from=period_start,
        date_to=period_end,
        contact=_contact_header(contact, company),
        summary=VendorLedgerStatementSummary(
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
        open_bills=_open_bill_rows(bills, now),
        aging_buckets=_aging_buckets(bills, now),
    )


@router.post("/export-log")
def export_log(
    payload: VendorLedgerExportLogRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_require_export),
):
    details = f"Vendor ledger export — contact {payload.contact_id} · {payload.period_label or payload.period} ({payload.row_count} rows)"
    log_activity(
        db,
        "vendor_ledger_exported",
        user_id=user.id,
        email=user.email,
        details=details,
        ip_address=get_client_ip(request),
    )
    return {"ok": True}
