from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth_utils import get_db, require_permission
from deal_config import PIPELINE_STAGES
from models import ClientNote, Company, Deal, FollowUpReminder, Invoice, Lead, Project, ProjectTask, Quotation, User
from permissions import role_has_permission
from projects_config import OPEN_TASK_STATUSES
from schemas import DashboardKpiResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKpiResponse)
def dashboard_kpis(
    user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    company = db.query(Company).first()
    if not company:
        return DashboardKpiResponse()

    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    week_end = start_of_day + timedelta(days=7)

    pipeline_value = (
        db.query(func.coalesce(func.sum(Deal.expected_value), 0))
        .filter(Deal.company_id == company.id, Deal.stage.in_(PIPELINE_STAGES))
        .scalar()
    )
    open_deals = (
        db.query(func.count(Deal.id))
        .filter(Deal.company_id == company.id, Deal.stage.in_(PIPELINE_STAGES))
        .scalar()
    )

    pending_quotes = (
        db.query(func.count(Quotation.id))
        .filter(
            Quotation.company_id == company.id,
            Quotation.status.in_(["draft", "pending_approval", "approved", "sent", "viewed", "negotiation"]),
        )
        .scalar()
    )

    outstanding_statuses = ["issued", "sent", "viewed", "partially_paid", "overdue"]
    overdue_invoices = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(outstanding_statuses),
            Invoice.outstanding_amount > 0,
            Invoice.due_date < now,
        )
        .scalar()
    )
    total_outstanding = (
        db.query(func.coalesce(func.sum(Invoice.outstanding_amount), 0))
        .filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(outstanding_statuses),
            Invoice.outstanding_amount > 0,
        )
        .scalar()
    )
    open_invoices = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(outstanding_statuses),
            Invoice.outstanding_amount > 0,
        )
        .scalar()
    )
    total_invoices = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.company_id == company.id)
        .scalar()
    )
    revenue_collected = (
        db.query(func.coalesce(func.sum(Invoice.amount_paid), 0))
        .filter(Invoice.company_id == company.id)
        .scalar()
    )
    revenue_billed = (
        db.query(func.coalesce(func.sum(Invoice.grand_total), 0))
        .filter(Invoice.company_id == company.id, Invoice.status.notin_(["draft", "cancelled"]))
        .scalar()
    )

    total_leads = db.query(func.count(Lead.id)).filter(Lead.company_id == company.id).scalar()
    open_leads = (
        db.query(func.count(Lead.id))
        .filter(Lead.company_id == company.id, Lead.status.in_(["open", "hot", "follow_up", "cold", "qualified"]))
        .scalar()
    )

    task_query = (
        db.query(ProjectTask)
        .join(Project, ProjectTask.project_id == Project.id)
        .filter(Project.company_id == company.id, ProjectTask.status.in_(OPEN_TASK_STATUSES))
    )
    if not role_has_permission(db, user.role, "projects.view_all"):
        task_query = task_query.filter(ProjectTask.assigned_to_id == user.id)

    tasks_overdue = task_query.filter(
        ProjectTask.due_date.isnot(None),
        ProjectTask.due_date < now,
    ).count()
    tasks_due = task_query.filter(
        ProjectTask.due_date.isnot(None),
        ProjectTask.due_date >= start_of_day,
        ProjectTask.due_date < week_end,
    ).count()

    reminder_due = (
        db.query(func.count(FollowUpReminder.id))
        .filter(
            FollowUpReminder.company_id == company.id,
            FollowUpReminder.status == "pending",
            FollowUpReminder.due_at >= start_of_day,
            FollowUpReminder.due_at < end_of_day,
        )
        .scalar()
    )
    reminder_overdue = (
        db.query(func.count(FollowUpReminder.id))
        .filter(
            FollowUpReminder.company_id == company.id,
            FollowUpReminder.status == "pending",
            FollowUpReminder.due_at < now,
        )
        .scalar()
    )
    note_overdue = (
        db.query(func.count(ClientNote.id))
        .filter(
            ClientNote.company_id == company.id,
            ClientNote.is_deleted.is_(False),
            ClientNote.follow_up_required.is_(True),
            ClientNote.follow_up_completed_at.is_(None),
            ClientNote.follow_up_due_date < now,
        )
        .scalar()
    )
    note_due_today = (
        db.query(func.count(ClientNote.id))
        .filter(
            ClientNote.company_id == company.id,
            ClientNote.is_deleted.is_(False),
            ClientNote.follow_up_required.is_(True),
            ClientNote.follow_up_completed_at.is_(None),
            ClientNote.follow_up_due_date >= start_of_day,
            ClientNote.follow_up_due_date < end_of_day,
        )
        .scalar()
    )

    outstanding_float = float(total_outstanding or 0)
    return DashboardKpiResponse(
        pipeline_value=float(pipeline_value or 0),
        open_deals=open_deals or 0,
        pending_quotes=pending_quotes or 0,
        overdue_invoices=overdue_invoices or 0,
        total_outstanding=outstanding_float,
        follow_ups_due_today=(reminder_due or 0) + (note_due_today or 0),
        follow_ups_overdue=(reminder_overdue or 0) + (note_overdue or 0),
        total_leads=total_leads or 0,
        open_leads=open_leads or 0,
        open_invoices=open_invoices or 0,
        total_invoices=total_invoices or 0,
        revenue_collected=float(revenue_collected or 0),
        revenue_billed=float(revenue_billed or 0),
        pending_payments=outstanding_float,
        tasks_due=tasks_due or 0,
        tasks_overdue=tasks_overdue or 0,
    )
