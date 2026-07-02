"""AI Reports business logic (Phase 1)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ai_reports_config import DOMAIN_PERMISSIONS, SEVERITY_ORDER
from deal_config import CLOSED_DEAL_STAGES, PIPELINE_STAGES
from field_service_config import OPEN_FSO_STATUSES
from models import (
    AiInsightRun,
    AiInsightSection,
    AiReportSettings,
    AttendanceRecord,
    Company,
    CustomerSubscription,
    Deal,
    EmployeeProfile,
    Expense,
    FieldServiceOrder,
    Invoice,
    Lead,
    LeaveRequest,
    MaintenanceAsset,
    MaintenanceWorkOrder,
    Product,
    QualityAlert,
    Quotation,
    RentalAsset,
    RentalContract,
    StockMovement,
    TimesheetEntry,
    User,
    WorkOrder,
)
from permissions import role_has_permission
from services.ai_insight_templates import RENDERERS, compose_executive
from services.notification_service import notify_role


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)


def _dt_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _dt_end(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)


def resolve_period(
    period: str | None,
    period_start: date | None,
    period_end: date | None,
) -> tuple[date, date]:
    today = date.today()
    if period_start and period_end:
        return period_start, period_end
    key = period or "30d"
    if key == "7d":
        return today - timedelta(days=6), today
    if key == "30d":
        return today - timedelta(days=29), today
    if key == "mtd":
        return today.replace(day=1), today
    if key == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    return today - timedelta(days=29), today


def prior_period(start: date, end: date) -> tuple[date, date]:
    days = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=days - 1)
    return prior_start, prior_end


def permitted_domains(db: Session, user: User) -> list[str]:
    allowed: list[str] = []
    for domain, perms in DOMAIN_PERMISSIONS.items():
        if any(role_has_permission(db, user.role, p) for p in perms):
            allowed.append(domain)
    return allowed


def generate_run_number(db: Session, company_id: int, prefix: str = "AIR") -> str:
    year = _utcnow().year
    pattern = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(AiInsightRun.id))
        .filter(AiInsightRun.company_id == company_id, AiInsightRun.run_number.like(pattern))
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def collect_sales_metrics(
    db: Session, company_id: int, start: date, end: date
) -> dict[str, Any]:
    ps, pe = prior_period(start, end)
    start_dt, end_dt = _dt_start(start), _dt_end(end)
    p_start_dt, p_end_dt = _dt_start(ps), _dt_end(pe)

    new_leads = (
        db.query(func.count(Lead.id))
        .filter(Lead.company_id == company_id, Lead.created_at >= start_dt, Lead.created_at <= end_dt)
        .scalar()
    )
    prior_new_leads = (
        db.query(func.count(Lead.id))
        .filter(Lead.company_id == company_id, Lead.created_at >= p_start_dt, Lead.created_at <= p_end_dt)
        .scalar()
    )
    pipeline_value = (
        db.query(func.coalesce(func.sum(Deal.expected_value), 0))
        .filter(Deal.company_id == company_id, Deal.stage.in_(PIPELINE_STAGES))
        .scalar()
    )
    open_deals = (
        db.query(func.count(Deal.id))
        .filter(Deal.company_id == company_id, Deal.stage.in_(PIPELINE_STAGES))
        .scalar()
    )
    stale_cutoff = _utcnow() - timedelta(days=30)
    stale_deals = (
        db.query(func.count(Deal.id))
        .filter(
            Deal.company_id == company_id,
            Deal.stage.in_(PIPELINE_STAGES),
            Deal.updated_at < stale_cutoff,
        )
        .scalar()
    )
    won_revenue = (
        db.query(func.coalesce(func.sum(Deal.expected_value), 0))
        .filter(
            Deal.company_id == company_id,
            Deal.stage == "won",
            Deal.closed_at >= start_dt,
            Deal.closed_at <= end_dt,
        )
        .scalar()
    )
    pending_quotes = (
        db.query(func.count(Quotation.id))
        .filter(
            Quotation.company_id == company_id,
            Quotation.status.in_(["draft", "pending_approval", "approved", "sent", "viewed", "negotiation"]),
        )
        .scalar()
    )
    return {
        "new_leads": int(new_leads or 0),
        "prior_new_leads": int(prior_new_leads or 0),
        "pipeline_value": _float(pipeline_value),
        "open_deals": int(open_deals or 0),
        "stale_deals": int(stale_deals or 0),
        "won_revenue": _float(won_revenue),
        "pending_quotes": int(pending_quotes or 0),
    }


def collect_finance_metrics(
    db: Session, company_id: int, start: date, end: date
) -> dict[str, Any]:
    ps, pe = prior_period(start, end)
    start_dt, end_dt = _dt_start(start), _dt_end(end)
    p_start_dt, p_end_dt = _dt_start(ps), _dt_end(pe)
    outstanding_statuses = ["issued", "sent", "viewed", "partially_paid", "overdue"]
    now = _utcnow()

    invoiced = (
        db.query(func.coalesce(func.sum(Invoice.grand_total), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.notin_(["draft", "cancelled"]),
            Invoice.issue_date >= start_dt,
            Invoice.issue_date <= end_dt,
        )
        .scalar()
    )
    collected = (
        db.query(func.coalesce(func.sum(Invoice.amount_paid), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.last_payment_at >= start_dt,
            Invoice.last_payment_at <= end_dt,
        )
        .scalar()
    )
    prior_collected = (
        db.query(func.coalesce(func.sum(Invoice.amount_paid), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.last_payment_at >= p_start_dt,
            Invoice.last_payment_at <= p_end_dt,
        )
        .scalar()
    )
    outstanding = (
        db.query(func.coalesce(func.sum(Invoice.outstanding_amount), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(outstanding_statuses),
            Invoice.outstanding_amount > 0,
        )
        .scalar()
    )
    overdue_count = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(outstanding_statuses),
            Invoice.outstanding_amount > 0,
            Invoice.due_date < now,
        )
        .scalar()
    )
    overdue_amount = (
        db.query(func.coalesce(func.sum(Invoice.outstanding_amount), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(outstanding_statuses),
            Invoice.outstanding_amount > 0,
            Invoice.due_date < now,
        )
        .scalar()
    )
    expenses = (
        db.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.company_id == company_id,
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
            Expense.status.in_(["approved", "paid"]),
        )
        .scalar()
    )
    return {
        "invoiced": _float(invoiced),
        "collected": _float(collected),
        "prior_collected": _float(prior_collected),
        "outstanding": _float(outstanding),
        "overdue_count": int(overdue_count or 0),
        "overdue_amount": _float(overdue_amount),
        "expenses": _float(expenses),
    }


def collect_inventory_metrics(
    db: Session, company_id: int, start: date, end: date
) -> dict[str, Any]:
    start_dt, end_dt = _dt_start(start), _dt_end(end)
    products = (
        db.query(Product)
        .filter(Product.company_id == company_id, Product.inventory_tracked.is_(True), Product.status == "active")
        .all()
    )
    low_stock = 0
    stock_value = 0.0
    for p in products:
        qty = _float(p.on_hand_quantity)
        stock_value += qty * _float(p.unit_valuation)
        if p.reorder_level is not None and qty <= _float(p.reorder_level):
            low_stock += 1

    movements_in = (
        db.query(func.count(StockMovement.id))
        .filter(
            StockMovement.company_id == company_id,
            StockMovement.direction == "in",
            StockMovement.movement_date >= start_dt,
            StockMovement.movement_date <= end_dt,
        )
        .scalar()
    )
    movements_out = (
        db.query(func.count(StockMovement.id))
        .filter(
            StockMovement.company_id == company_id,
            StockMovement.direction == "out",
            StockMovement.movement_date >= start_dt,
            StockMovement.movement_date <= end_dt,
        )
        .scalar()
    )
    return {
        "tracked_skus": len(products),
        "low_stock_count": low_stock,
        "stock_value": stock_value,
        "movements_in": int(movements_in or 0),
        "movements_out": int(movements_out or 0),
    }


def collect_hr_metrics(
    db: Session, company_id: int, start: date, end: date
) -> dict[str, Any]:
    start_dt, end_dt = _dt_start(start), _dt_end(end)
    headcount = (
        db.query(func.count(EmployeeProfile.id))
        .filter(EmployeeProfile.company_id == company_id)
        .scalar()
    )
    attendance_rows = (
        db.query(AttendanceRecord.status, func.count(AttendanceRecord.id))
        .filter(
            AttendanceRecord.company_id == company_id,
            AttendanceRecord.attendance_date >= start_dt,
            AttendanceRecord.attendance_date <= end_dt,
        )
        .group_by(AttendanceRecord.status)
        .all()
    )
    total_att = sum(int(c) for _, c in attendance_rows)
    present = sum(int(c) for s, c in attendance_rows if s == "present")
    attendance_rate = (present / total_att * 100) if total_att > 0 else 0.0

    leave_pending = (
        db.query(func.count(LeaveRequest.id))
        .filter(LeaveRequest.company_id == company_id, LeaveRequest.status == "pending")
        .scalar()
    )
    timesheet_hours = (
        db.query(func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .filter(
            TimesheetEntry.company_id == company_id,
            TimesheetEntry.work_date >= start_dt,
            TimesheetEntry.work_date <= end_dt,
        )
        .scalar()
    )
    return {
        "headcount": int(headcount or 0),
        "attendance_rate": attendance_rate,
        "leave_pending": int(leave_pending or 0),
        "timesheet_hours": _float(timesheet_hours),
    }


def collect_operations_metrics(
    db: Session, company_id: int, start: date, end: date
) -> dict[str, Any]:
    now = _utcnow()
    open_mfg_wo = (
        db.query(func.count(WorkOrder.id))
        .filter(WorkOrder.company_id == company_id, WorkOrder.status.notin_(["completed", "cancelled"]))
        .scalar()
    )
    quality_alerts = (
        db.query(func.count(QualityAlert.id))
        .filter(QualityAlert.company_id == company_id, QualityAlert.status == "open")
        .scalar()
    )
    pm_overdue = (
        db.query(func.count(MaintenanceAsset.id))
        .filter(
            MaintenanceAsset.company_id == company_id,
            MaintenanceAsset.status == "active",
            MaintenanceAsset.next_pm_due_date.isnot(None),
            MaintenanceAsset.next_pm_due_date < date.today(),
        )
        .scalar()
    )
    open_fso = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(FieldServiceOrder.company_id == company_id, FieldServiceOrder.status.in_(OPEN_FSO_STATUSES))
        .scalar()
    )
    sla_breached = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(
            FieldServiceOrder.company_id == company_id,
            FieldServiceOrder.status.in_(OPEN_FSO_STATUSES),
            FieldServiceOrder.sla_due_at.isnot(None),
            FieldServiceOrder.sla_due_at < now,
        )
        .scalar()
    )
    subs_past_due = (
        db.query(func.count(CustomerSubscription.id))
        .filter(CustomerSubscription.company_id == company_id, CustomerSubscription.status == "past_due")
        .scalar()
    )
    week_end = date.today() + timedelta(days=7)
    renewals_due = (
        db.query(func.count(CustomerSubscription.id))
        .filter(
            CustomerSubscription.company_id == company_id,
            CustomerSubscription.status.in_(("active", "trialing", "past_due")),
            CustomerSubscription.next_billing_date.isnot(None),
            CustomerSubscription.next_billing_date <= week_end,
            CustomerSubscription.next_billing_date >= date.today(),
        )
        .scalar()
    )
    rental_overdue = (
        db.query(func.count(RentalContract.id))
        .filter(
            RentalContract.company_id == company_id,
            RentalContract.status.in_(("on_rent", "delivered", "return_scheduled")),
            RentalContract.rental_end < now,
        )
        .scalar()
    )
    total_units = (
        db.query(func.coalesce(func.sum(RentalAsset.quantity_available), 0))
        .filter(RentalAsset.company_id == company_id, RentalAsset.status == "active")
        .scalar()
    )
    on_rent = (
        db.query(func.coalesce(func.sum(MaintenanceWorkOrder.id), 0))
        .filter(MaintenanceWorkOrder.company_id == company_id, MaintenanceWorkOrder.status.notin_(("completed", "cancelled")))
        .scalar()
    )
    utilization = 0.0
    if total_units and int(total_units) > 0:
        active_rentals = (
            db.query(func.count(RentalContract.id))
            .filter(RentalContract.company_id == company_id, RentalContract.status.in_(("on_rent", "delivered")))
            .scalar()
        )
        utilization = min(100.0, (int(active_rentals or 0) / int(total_units)) * 100)

    return {
        "open_mfg_wo": int(open_mfg_wo or 0),
        "quality_alerts": int(quality_alerts or 0),
        "pm_overdue": int(pm_overdue or 0),
        "open_fso": int(open_fso or 0),
        "sla_breached": int(sla_breached or 0),
        "subs_past_due": int(subs_past_due or 0),
        "renewals_due": int(renewals_due or 0),
        "rental_overdue": int(rental_overdue or 0),
        "rental_utilization": utilization,
        "open_mwo": int(on_rent or 0),
    }


COLLECTORS = {
    "sales": collect_sales_metrics,
    "finance": collect_finance_metrics,
    "inventory": collect_inventory_metrics,
    "hr": collect_hr_metrics,
    "operations": collect_operations_metrics,
}


def generate_domain_section(domain: str, metrics: dict) -> dict:
    renderer = RENDERERS.get(domain)
    if not renderer:
        return {
            "headline": f"{domain.title()} insights",
            "narrative": "No template available.",
            "bullets": [],
            "watch_items": [],
        }
    result = renderer(metrics)
    result["metrics"] = metrics
    return result


def rank_watch_items(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda w: SEVERITY_ORDER.get(w.get("severity", "low"), 9))


def run_insight_generation(
    db: Session,
    company: Company,
    user: User,
    settings: AiReportSettings,
    run: AiInsightRun,
    domains: list[str],
    include_executive: bool,
) -> AiInsightRun:
    allowed = set(permitted_domains(db, user))
    target_domains = [d for d in domains if d in allowed and d != "executive"]
    if not target_domains:
        run.status = "failed"
        run.error_message = "No permitted domains to generate"
        run.completed_at = _utcnow()
        return run

    section_results: list[dict] = []
    all_watch: list[dict] = []
    errors: list[str] = []

    for idx, domain in enumerate(target_domains):
        try:
            collector = COLLECTORS[domain]
            metrics = collector(db, company.id, run.period_start, run.period_end)
            rendered = generate_domain_section(domain, metrics)
            section = AiInsightSection(
                run_id=run.id,
                domain=domain,
                headline=rendered["headline"],
                narrative=rendered["narrative"],
                bullets_json=rendered.get("bullets", []),
                watch_items_json=rendered.get("watch_items", []),
                metrics_json=rendered.get("metrics", metrics),
                sort_order=idx,
            )
            db.add(section)
            section_results.append(rendered)
            all_watch.extend(rendered.get("watch_items", []))
        except Exception as exc:  # noqa: BLE001 — partial run per PRD
            errors.append(f"{domain}: {exc}")

    if include_executive and section_results:
        exec_data = compose_executive(section_results, all_watch)
        exec_section = AiInsightSection(
            run_id=run.id,
            domain="executive",
            headline=exec_data["headline"],
            narrative=exec_data["summary"],
            bullets_json=[],
            watch_items_json=rank_watch_items(all_watch)[:5],
            metrics_json={},
            sort_order=99,
        )
        db.add(exec_section)
        run.executive_headline = exec_data["headline"]
        run.executive_summary = exec_data["summary"]

    run.domains_json = target_domains
    if not section_results and errors:
        run.status = "failed"
        run.error_message = "; ".join(errors)
    else:
        run.status = "completed"
        if errors:
            run.error_message = "Partial: " + "; ".join(errors)
    run.completed_at = _utcnow()

    roles = settings.notify_roles_json or []
    for role in roles:
        notify_role(
            db,
            company_id=company.id,
            role=role,
            category="ai_insight",
            title=f"AI insight ready — {run.run_number}",
            message=run.executive_headline or "New insight brief generated.",
            link_path=f"/ai-reports/runs/{run.id}",
        )
    return run


def aggregate_watch_from_run(run: AiInsightRun) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for section in run.sections or []:
        for w in section.watch_items_json or []:
            key = f"{w.get('severity', '')}|{w.get('text', '')}|{w.get('link_path', '')}"
            if key in seen:
                continue
            seen.add(key)
            items.append(w)
    return rank_watch_items(items)[:10]
