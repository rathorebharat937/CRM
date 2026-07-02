"""Rental Management business logic (Phase 1)."""

from __future__ import annotations

import math
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from invoice_config import DEFAULT_BANK_INSTRUCTIONS, DEFAULT_BILLING_NOTES, DEFAULT_PAYMENT_TERMS
from models import (
    Company,
    Contact,
    Invoice,
    InvoiceLineItem,
    RentalAsset,
    RentalContract,
    RentalContractLine,
    RentalDeposit,
    RentalInvoice,
    RentalSettings,
    User,
)
from rental_config import DEPOSIT_TYPES, RATE_BASIS_OPTIONS, RESERVED_STATUSES, RETURN_CONDITIONS
from services.document_number_service import generate_invoice_number
from services.notification_service import notify_role


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)


def rental_days(start: datetime, end: datetime) -> int:
    delta = end - start
    days = max(1, math.ceil(delta.total_seconds() / 86400))
    return days


def unit_rate_for_basis(asset: RentalAsset, rate_basis: str) -> Decimal | None:
    if rate_basis == "daily" and asset.rate_daily is not None:
        return Decimal(str(asset.rate_daily))
    if rate_basis == "weekly" and asset.rate_weekly is not None:
        return Decimal(str(asset.rate_weekly))
    if rate_basis == "monthly" and asset.rate_monthly is not None:
        return Decimal(str(asset.rate_monthly))
    if asset.rate_daily is not None:
        return Decimal(str(asset.rate_daily))
    if asset.rate_weekly is not None:
        return Decimal(str(asset.rate_weekly))
    if asset.rate_monthly is not None:
        return Decimal(str(asset.rate_monthly))
    return None


def compute_line_pricing(
    asset: RentalAsset,
    quantity: int,
    rate_basis: str,
    start: datetime,
    end: datetime,
) -> tuple[int, Decimal, Decimal, Decimal, Decimal]:
    days = rental_days(start, end)
    rate = unit_rate_for_basis(asset, rate_basis)
    if rate is None:
        raise ValueError(f"No rate configured for asset {asset.asset_code}")

    qty = Decimal(str(quantity))
    gst = Decimal(str(asset.gst_rate or 18))

    if rate_basis == "weekly":
        periods = max(1, math.ceil(days / 7))
        line_subtotal = rate * Decimal(str(periods)) * qty
    elif rate_basis == "monthly":
        periods = max(1, math.ceil(days / 30))
        line_subtotal = rate * Decimal(str(periods)) * qty
    else:
        line_subtotal = rate * Decimal(str(days)) * qty

    tax = line_subtotal * gst / Decimal("100")
    line_total = line_subtotal + tax
    return days, rate, line_subtotal, gst, line_total


def compute_contract_totals(
    lines: list[RentalContractLine],
    settings: RentalSettings,
    assets: dict[int, RentalAsset],
) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = Decimal("0")
    grand_total = Decimal("0")
    fixed_deposit = Decimal("0")
    has_fixed = False

    for line in lines:
        subtotal += Decimal(str(line.line_subtotal))
        grand_total += Decimal(str(line.line_total))
        asset = assets.get(line.rental_asset_id)
        if asset and asset.deposit_amount is not None:
            fixed_deposit += Decimal(str(asset.deposit_amount)) * Decimal(str(line.quantity))
            has_fixed = True

    if has_fixed:
        deposit_required = fixed_deposit
    else:
        pct = Decimal(str(settings.default_deposit_percent or 20)) / Decimal("100")
        deposit_required = (subtotal * pct).quantize(Decimal("0.01"))

    return subtotal, grand_total, deposit_required


def generate_contract_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    pattern = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(RentalContract.id))
        .filter(RentalContract.company_id == company_id, RentalContract.contract_number.like(pattern))
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _ranges_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def check_availability(
    db: Session,
    company_id: int,
    asset_id: int,
    quantity: int,
    start: datetime,
    end: datetime,
    exclude_contract_id: int | None = None,
    allow_overbook: bool = False,
) -> list[str]:
    if allow_overbook:
        return []

    asset = (
        db.query(RentalAsset)
        .filter(RentalAsset.id == asset_id, RentalAsset.company_id == company_id)
        .first()
    )
    if not asset:
        return [f"Asset {asset_id} not found"]
    if asset.status in ("retired", "maintenance"):
        return [f"{asset.asset_code} is {asset.status} and unavailable"]

    q = (
        db.query(RentalContractLine)
        .join(RentalContract, RentalContractLine.contract_id == RentalContract.id)
        .filter(
            RentalContract.company_id == company_id,
            RentalContract.status.in_(RESERVED_STATUSES),
            RentalContractLine.rental_asset_id == asset_id,
        )
    )
    if exclude_contract_id:
        q = q.filter(RentalContract.id != exclude_contract_id)

    booked = 0
    conflicts: list[str] = []
    for line in q.all():
        contract = line.contract
        if not contract:
            continue
        if _ranges_overlap(start, end, contract.rental_start, contract.rental_end):
            booked += int(line.quantity or 0)
            conflicts.append(
                f"{asset.asset_code}: {line.quantity} unit(s) booked on {contract.contract_number}"
            )

    if booked + quantity > int(asset.quantity_available or 0):
        conflicts.append(
            f"{asset.asset_code}: only {asset.quantity_available} available, "
            f"{booked} already booked, requested {quantity}"
        )
    return conflicts


def deposit_held(contract: RentalContract) -> Decimal:
    received = Decimal(str(contract.deposit_received or 0))
    refunded = Decimal(str(contract.deposit_refunded or 0))
    deducted = Decimal(str(contract.deposit_deducted or 0))
    return received - refunded - deducted


def sync_deposit_totals(contract: RentalContract) -> None:
    received = Decimal("0")
    refunded = Decimal("0")
    deducted = Decimal("0")
    for row in contract.deposits or []:
        amt = Decimal(str(row.amount))
        if row.type == "received":
            received += amt
        elif row.type == "refund":
            refunded += amt
        elif row.type == "deduction":
            deducted += amt
    contract.deposit_received = received
    contract.deposit_refunded = refunded
    contract.deposit_deducted = deducted


def compute_late_fee(
    contract: RentalContract,
    settings: RentalSettings,
    actual_return: datetime,
) -> Decimal:
    grace = timedelta(hours=int(settings.grace_hours_after_due or 24))
    due_with_grace = contract.rental_end + grace
    if actual_return <= due_with_grace:
        return Decimal("0")
    late_seconds = (actual_return - due_with_grace).total_seconds()
    late_days = max(1, math.ceil(late_seconds / 86400))
    fee = Decimal(str(settings.late_fee_per_day or 0)) * Decimal(str(late_days))
    return fee.quantize(Decimal("0.01"))


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


def create_contract_invoice(
    db: Session,
    company: Company,
    user: User,
    contract: RentalContract,
    settings: RentalSettings,
    invoice_type: str = "rental",
    extra_lines: list[dict] | None = None,
) -> Invoice:
    contact = contract.contact
    billing = _contact_billing(contact) if contact else {}
    issue_mode = settings.auto_invoice_mode or "draft"
    status = "issued" if issue_mode == "issue" else "draft"
    now = _utcnow()

    subtotal = Decimal("0")
    total_tax = Decimal("0")
    grand_total = Decimal("0")

    inv = Invoice(
        company_id=company.id,
        created_by_id=user.id,
        issued_by_id=user.id if status == "issued" else None,
        contact_id=contract.contact_id,
        title=f"Rental {contract.contract_number}",
        status=status,
        invoice_type="standard",
        source_type="manual",
        currency=company.currency or "INR",
        issue_date=now,
        due_date=now + timedelta(days=7),
        requires_review=0,
        internal_notes=f"Generated for rental contract {contract.contract_number} ({invoice_type})",
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

    sort_idx = 0
    if invoice_type == "rental":
        for line in contract.lines or []:
            ls = Decimal(str(line.line_subtotal))
            lt = Decimal(str(line.line_total))
            tax = lt - ls
            subtotal += ls
            total_tax += tax
            grand_total += lt
            asset = line.rental_asset
            inv.line_items.append(
                InvoiceLineItem(
                    product_id=asset.product_id if asset else None,
                    sort_order=sort_idx,
                    item_name=asset.name if asset else "Rental item",
                    description=f"Rental {contract.rental_start.date()} to {contract.rental_end.date()}",
                    quantity=Decimal(str(line.quantity)),
                    unit="Nos",
                    unit_price=Decimal(str(line.unit_rate)),
                    tax_rate=Decimal(str(line.gst_rate)),
                    line_subtotal=ls,
                    line_total=lt,
                )
            )
            sort_idx += 1
    elif extra_lines:
        for item in extra_lines:
            ls = Decimal(str(item["line_subtotal"]))
            lt = Decimal(str(item["line_total"]))
            tax = lt - ls
            subtotal += ls
            total_tax += tax
            grand_total += lt
            inv.line_items.append(
                InvoiceLineItem(
                    sort_order=sort_idx,
                    item_name=item["name"],
                    description=item.get("description"),
                    quantity=Decimal("1"),
                    unit="Service",
                    unit_price=ls,
                    tax_rate=Decimal(str(item.get("gst_rate", 18))),
                    line_subtotal=ls,
                    line_total=lt,
                )
            )
            sort_idx += 1

    inv.subtotal = subtotal
    inv.total_tax = total_tax
    inv.grand_total = grand_total
    inv.outstanding_amount = grand_total
    inv.amount_paid = Decimal("0")

    link = RentalInvoice(
        contract_id=contract.id,
        invoice_id=inv.id,
        invoice_type=invoice_type,
        generated_at=now,
    )
    db.add(link)
    return inv


def send_rental_reminders(db: Session, company: Company, settings: RentalSettings) -> int:
    if not settings.is_enabled:
        return 0
    now = _utcnow()
    roles = settings.notify_roles_json or []
    sent = 0

    contracts = (
        db.query(RentalContract)
        .options(joinedload(RentalContract.contact))
        .filter(
            RentalContract.company_id == company.id,
            RentalContract.status.in_(("confirmed", "on_rent", "return_scheduled", "delivered")),
        )
        .all()
    )

    for contract in contracts:
        link = f"/rental/contracts/{contract.id}"
        contact_name = contract.contact.name if contract.contact else "Customer"

        if contract.delivery_scheduled_at:
            hours = (contract.delivery_scheduled_at - now).total_seconds() / 3600
            if 0 <= hours <= 24 and contract.status == "confirmed":
                title = f"Delivery today — {contract.contract_number}"
                message = f"Deliver to {contact_name}."
                for role in roles:
                    notify_role(
                        db,
                        company_id=company.id,
                        role=role,
                        category="rental_delivery",
                        title=title,
                        message=message,
                        link_path=link,
                        dedupe_per_day=True,
                    )
                sent += 1

        hours_to_return = (contract.rental_end - now).total_seconds() / 3600
        if 0 <= hours_to_return <= 168 and contract.status in ("on_rent", "delivered", "return_scheduled"):
            if hours_to_return <= 24:
                title = f"Return due today — {contract.contract_number}"
            else:
                title = f"Return due soon — {contract.contract_number}"
            message = f"{contact_name} return due {contract.rental_end.isoformat()}."
            for role in roles:
                notify_role(
                    db,
                    company_id=company.id,
                    role=role,
                    category="rental_return",
                    title=title,
                    message=message,
                    link_path=link,
                    dedupe_per_day=True,
                )
            sent += 1

        if now > contract.rental_end and contract.status in ("on_rent", "return_scheduled", "delivered"):
            title = f"Overdue return — {contract.contract_number}"
            message = f"{contact_name} overdue since {contract.rental_end.isoformat()}."
            for role in roles:
                notify_role(
                    db,
                    company_id=company.id,
                    role=role,
                    category="rental_overdue",
                    title=title,
                    message=message,
                    link_path=link,
                    dedupe_per_day=True,
                )
            sent += 1

    return sent


def validate_rate_basis(rate_basis: str) -> None:
    if rate_basis not in RATE_BASIS_OPTIONS:
        raise ValueError(f"Invalid rate basis: {rate_basis}")


def validate_return_condition(condition: str) -> None:
    if condition not in RETURN_CONDITIONS:
        raise ValueError(f"Invalid return condition: {condition}")


def validate_deposit_type(dep_type: str) -> None:
    if dep_type not in DEPOSIT_TYPES:
        raise ValueError(f"Invalid deposit type: {dep_type}")
