from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import STAFF_ROLES
from models import (
    Company,
    Contact,
    Deal,
    Project,
    ProjectMember,
    ProjectTask,
    SalesOrder,
    User,
)
from permissions import role_has_permission
from projects_config import (
    LOCKED_TASK_PROJECT_STATUSES,
    MEMBER_ROLE_LABELS,
    MEMBER_ROLES,
    OPEN_TASK_STATUSES,
    PROJECT_PRIORITIES,
    PROJECT_PRIORITY_LABELS,
    PROJECT_STAGE_LABELS,
    PROJECT_STAGES,
    PROJECT_STATUS_LABELS,
    PROJECT_STATUSES,
    PROJECT_TYPE_LABELS,
    PROJECT_TYPES,
    TASK_STATUS_LABELS,
    TASK_STATUSES,
    TERMINAL_PROJECT_STATUSES,
)
from schemas import (
    ProjectContactSummaryResponse,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectExportLogRequest,
    ProjectIndexKpis,
    ProjectListResponse,
    ProjectListRow,
    ProjectMemberAddRequest,
    ProjectMemberResponse,
    ProjectMetaResponse,
    ProjectMyTaskRow,
    ProjectMyTasksResponse,
    ProjectOption,
    ProjectStageSummary,
    ProjectStatusChangeRequest,
    ProjectTaskCreateRequest,
    ProjectTaskResponse,
    ProjectTaskUpdateRequest,
    ProjectUpdateRequest,
    StaffAssigneeResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today_start() -> datetime:
    now = _utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)




def _validate_project_status(status: str) -> None:
    if status not in PROJECT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(PROJECT_STATUSES)}")


def _validate_project_type(project_type: str) -> None:
    if project_type not in PROJECT_TYPES:
        raise HTTPException(status_code=400, detail=f"Project type must be one of: {', '.join(PROJECT_TYPES)}")


def _validate_priority(priority: str) -> None:
    if priority not in PROJECT_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Priority must be one of: {', '.join(PROJECT_PRIORITIES)}")


def _validate_task_status(status: str) -> None:
    if status not in TASK_STATUSES:
        raise HTTPException(status_code=400, detail=f"Task status must be one of: {', '.join(TASK_STATUSES)}")


def _validate_stage(stage_key: str) -> None:
    if stage_key not in PROJECT_STAGES:
        raise HTTPException(status_code=400, detail=f"Stage must be one of: {', '.join(PROJECT_STAGES)}")


def _validate_member_role(role: str) -> None:
    if role not in MEMBER_ROLES:
        raise HTTPException(status_code=400, detail=f"Member role must be one of: {', '.join(MEMBER_ROLES)}")


def _validate_staff(db: Session, user_id: int | None, company_id: int, field: str = "Staff member") -> None:
    if user_id is None:
        return
    staff = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.company_id == company_id,
            User.role.in_(STAFF_ROLES),
            User.status == "active",
        )
        .first()
    )
    if not staff:
        raise HTTPException(status_code=400, detail=f"Invalid {field.lower()}")


def _user_has_view_all(user: User, db: Session) -> bool:
    return role_has_permission(db, user.role, "projects.view_all")


def _accessible_project_filter(user: User, db: Session, company_id: int):
    if _user_has_view_all(user, db):
        return Project.company_id == company_id

    member_project_ids = (
        db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user.id).subquery()
    )
    task_project_ids = (
        db.query(ProjectTask.project_id)
        .filter(ProjectTask.assigned_to_id == user.id)
        .distinct()
        .subquery()
    )
    return and_(
        Project.company_id == company_id,
        or_(
            Project.project_manager_id == user.id,
            Project.id.in_(member_project_ids),
            Project.id.in_(task_project_ids),
        ),
    )


def _get_project(db: Session, project_id: int, company_id: int) -> Project:
    project = (
        db.query(Project)
        .options(
            joinedload(Project.contact),
            joinedload(Project.deal),
            joinedload(Project.sales_order),
            joinedload(Project.project_manager),
            joinedload(Project.members).joinedload(ProjectMember.user),
            joinedload(Project.tasks).joinedload(ProjectTask.assigned_to),
        )
        .filter(Project.id == project_id, Project.company_id == company_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _ensure_project_access(db: Session, user: User, project: Project) -> None:
    if _user_has_view_all(user, db):
        return
    if project.project_manager_id == user.id:
        return
    if any(m.user_id == user.id for m in project.members):
        return
    if any(t.assigned_to_id == user.id for t in project.tasks):
        return
    raise HTTPException(status_code=403, detail="You do not have access to this project")


def _can_manage_tasks(user: User, db: Session, project: Project) -> bool:
    if not role_has_permission(db, user.role, "projects.manage_tasks"):
        return False
    if project.status in LOCKED_TASK_PROJECT_STATUSES:
        return role_has_permission(db, user.role, "projects.edit")
    if _user_has_view_all(user, db):
        return True
    if project.project_manager_id == user.id:
        return True
    if any(m.user_id == user.id for m in project.members):
        return True
    return False


def _can_edit_project(user: User, db: Session) -> bool:
    return role_has_permission(db, user.role, "projects.edit")


def _generate_project_number(db: Session, company: Company) -> str:
    year = _utcnow().year
    prefix = f"PRJ-{year}-"
    last = (
        db.query(Project)
        .filter(Project.company_id == company.id, Project.project_number.like(f"{prefix}%"))
        .order_by(Project.id.desc())
        .first()
    )
    seq = 1
    if last and last.project_number:
        try:
            seq = int(last.project_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _is_task_overdue(task: ProjectTask, now: datetime | None = None) -> bool:
    if not task.due_date:
        return False
    if task.status in ("done", "cancelled"):
        return False
    ref = now or _utcnow()
    due = task.due_date if task.due_date.tzinfo else task.due_date.replace(tzinfo=timezone.utc)
    return due < ref


def _is_project_overdue(project: Project, now: datetime | None = None) -> bool:
    if not project.deadline or project.status != "active":
        return False
    ref = now or _utcnow()
    deadline = project.deadline if project.deadline.tzinfo else project.deadline.replace(tzinfo=timezone.utc)
    return deadline < ref


def _compute_task_stats(tasks: list[ProjectTask]) -> dict:
    active_tasks = [t for t in tasks if t.status != "cancelled"]
    done = sum(1 for t in active_tasks if t.status == "done")
    total = len(active_tasks)
    open_count = sum(1 for t in tasks if t.status in OPEN_TASK_STATUSES)
    overdue = sum(1 for t in tasks if _is_task_overdue(t))
    blocked = sum(1 for t in tasks if t.status == "blocked")
    unassigned = sum(
        1 for t in tasks
        if t.assigned_to_id is None and t.status not in ("done", "cancelled")
    )
    progress = round((done / total) * 100, 1) if total else 0.0
    return {
        "total": total,
        "done": done,
        "open_count": open_count,
        "overdue": overdue,
        "blocked": blocked,
        "unassigned": unassigned,
        "progress": progress,
    }


def _current_stage_summary(tasks: list[ProjectTask]) -> str | None:
    if not tasks:
        return None
    stage_counts: dict[str, dict[str, int]] = {}
    for stage in PROJECT_STAGES:
        stage_counts[stage] = {"total": 0, "done": 0}
    for task in tasks:
        if task.status == "cancelled":
            continue
        key = task.stage_key if task.stage_key in PROJECT_STAGES else "kickoff"
        stage_counts[key]["total"] += 1
        if task.status == "done":
            stage_counts[key]["done"] += 1
    for stage in PROJECT_STAGES:
        counts = stage_counts[stage]
        if counts["total"] > 0 and counts["done"] < counts["total"]:
            return PROJECT_STAGE_LABELS[stage]
    for stage in reversed(PROJECT_STAGES):
        if stage_counts[stage]["total"] > 0:
            return PROJECT_STAGE_LABELS[stage]
    return PROJECT_STAGE_LABELS["kickoff"]


def _build_stage_summaries(tasks: list[ProjectTask]) -> list[ProjectStageSummary]:
    summaries: list[ProjectStageSummary] = []
    for stage in PROJECT_STAGES:
        stage_tasks = [t for t in tasks if t.stage_key == stage and t.status != "cancelled"]
        done = sum(1 for t in stage_tasks if t.status == "done")
        overdue = sum(1 for t in stage_tasks if _is_task_overdue(t))
        summaries.append(
            ProjectStageSummary(
                stage_key=stage,
                stage_label=PROJECT_STAGE_LABELS[stage],
                total_tasks=len(stage_tasks),
                done_tasks=done,
                overdue_tasks=overdue,
            )
        )
    return summaries


def _task_resp(task: ProjectTask) -> ProjectTaskResponse:
    return ProjectTaskResponse(
        id=task.id,
        project_id=task.project_id,
        stage_key=task.stage_key,
        stage_label=PROJECT_STAGE_LABELS.get(task.stage_key, task.stage_key),
        title=task.title,
        description=task.description,
        assigned_to_id=task.assigned_to_id,
        assigned_to_name=task.assigned_to.name if task.assigned_to else None,
        status=task.status,
        status_label=TASK_STATUS_LABELS.get(task.status, task.status),
        priority=task.priority,
        priority_label=PROJECT_PRIORITY_LABELS.get(task.priority, task.priority),
        due_date=task.due_date,
        completed_at=task.completed_at,
        sort_order=task.sort_order,
        blocked_reason=task.blocked_reason,
        is_overdue=_is_task_overdue(task),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _member_resp(member: ProjectMember) -> ProjectMemberResponse:
    return ProjectMemberResponse(
        id=member.id,
        user_id=member.user_id,
        user_name=member.user.name if member.user else None,
        user_email=member.user.email if member.user else None,
        role=member.role,
        role_label=MEMBER_ROLE_LABELS.get(member.role, member.role),
        added_at=member.added_at,
    )


def _project_list_row(project: Project, tasks: list[ProjectTask] | None = None) -> ProjectListRow:
    task_list = tasks if tasks is not None else list(project.tasks or [])
    stats = _compute_task_stats(task_list)
    return ProjectListRow(
        id=project.id,
        project_number=project.project_number,
        name=project.name,
        project_type=project.project_type,
        status=project.status,
        status_label=PROJECT_STATUS_LABELS.get(project.status, project.status),
        priority=project.priority,
        priority_label=PROJECT_PRIORITY_LABELS.get(project.priority, project.priority),
        contact_id=project.contact_id,
        contact_name=project.contact.name if project.contact else None,
        project_manager_id=project.project_manager_id,
        project_manager_name=project.project_manager.name if project.project_manager else None,
        deadline=project.deadline,
        progress_percent=stats["progress"],
        stage_summary=_current_stage_summary(task_list),
        open_task_count=stats["open_count"],
        overdue_task_count=stats["overdue"],
        is_overdue=_is_project_overdue(project),
        updated_at=project.updated_at,
    )


def _project_detail_resp(project: Project) -> ProjectDetailResponse:
    tasks = sorted(project.tasks or [], key=lambda t: (PROJECT_STAGES.index(t.stage_key) if t.stage_key in PROJECT_STAGES else 99, t.sort_order, t.id))
    stats = _compute_task_stats(tasks)
    members = sorted(project.members or [], key=lambda m: (0 if m.role == "manager" else 1, m.user.name if m.user else ""))
    return ProjectDetailResponse(
        id=project.id,
        project_number=project.project_number,
        name=project.name,
        description=project.description,
        project_type=project.project_type,
        project_type_label=PROJECT_TYPE_LABELS.get(project.project_type, project.project_type),
        status=project.status,
        status_label=PROJECT_STATUS_LABELS.get(project.status, project.status),
        priority=project.priority,
        priority_label=PROJECT_PRIORITY_LABELS.get(project.priority, project.priority),
        contact_id=project.contact_id,
        contact_name=project.contact.name if project.contact else None,
        deal_id=project.deal_id,
        deal_title=project.deal.title if project.deal else None,
        sales_order_id=project.sales_order_id,
        sales_order_number=project.sales_order.order_number if project.sales_order else None,
        project_manager_id=project.project_manager_id,
        project_manager_name=project.project_manager.name if project.project_manager else None,
        created_by_id=project.created_by_id,
        start_date=project.start_date,
        deadline=project.deadline,
        completed_at=project.completed_at,
        progress_percent=stats["progress"],
        total_tasks=stats["total"],
        done_tasks=stats["done"],
        open_task_count=stats["open_count"],
        overdue_task_count=stats["overdue"],
        blocked_task_count=stats["blocked"],
        unassigned_task_count=stats["unassigned"],
        is_overdue=_is_project_overdue(project),
        is_locked=project.status in LOCKED_TASK_PROJECT_STATUSES,
        stage_summaries=_build_stage_summaries(tasks),
        tasks=[_task_resp(t) for t in tasks],
        members=[_member_resp(m) for m in members],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _ensure_assignee_is_member(
    db: Session,
    project: Project,
    user_id: int | None,
    added_by_id: int | None,
) -> None:
    if not user_id or user_id == project.project_manager_id:
        return
    existing = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id, ProjectMember.user_id == user_id)
        .first()
    )
    if not existing:
        db.add(
            ProjectMember(
                project_id=project.id,
                user_id=user_id,
                role="member",
                added_by_id=added_by_id,
            )
        )


def _validate_dates(start_date: datetime | None, deadline: datetime | None) -> None:
    if start_date and deadline and deadline < start_date:
        raise HTTPException(status_code=400, detail="Deadline must be on or after start date")


def _validate_links(db: Session, company_id: int, contact_id: int | None, deal_id: int | None, sales_order_id: int | None) -> None:
    if contact_id:
        contact = db.query(Contact).filter(Contact.id == contact_id, Contact.company_id == company_id).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact not found")
    if deal_id:
        deal = db.query(Deal).filter(Deal.id == deal_id, Deal.company_id == company_id).first()
        if not deal:
            raise HTTPException(status_code=400, detail="Deal not found")
    if sales_order_id:
        order = db.query(SalesOrder).filter(SalesOrder.id == sales_order_id, SalesOrder.company_id == company_id).first()
        if not order:
            raise HTTPException(status_code=400, detail="Sales order not found")


@router.get("/meta", response_model=ProjectMetaResponse)
def project_meta(_: User = Depends(require_permission("projects.view")), db: Session = Depends(get_db)):
    return ProjectMetaResponse(
        statuses=[ProjectOption(value=s, label=PROJECT_STATUS_LABELS[s]) for s in PROJECT_STATUSES],
        stages=[ProjectOption(value=s, label=PROJECT_STAGE_LABELS[s]) for s in PROJECT_STAGES],
        task_statuses=[ProjectOption(value=s, label=TASK_STATUS_LABELS[s]) for s in TASK_STATUSES],
        priorities=[ProjectOption(value=p, label=PROJECT_PRIORITY_LABELS[p]) for p in PROJECT_PRIORITIES],
        project_types=[ProjectOption(value=t, label=PROJECT_TYPE_LABELS[t]) for t in PROJECT_TYPES],
    )


@router.get("/assignees", response_model=list[StaffAssigneeResponse])
def project_assignees(user: User = Depends(require_permission("projects.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    staff = (
        db.query(User)
        .filter(User.company_id == company.id, User.role.in_(STAFF_ROLES), User.status == "active")
        .order_by(User.name)
        .all()
    )
    return [StaffAssigneeResponse(id=u.id, name=u.name, email=u.email, role=u.role) for u in staff]


@router.get("/my-tasks", response_model=ProjectMyTasksResponse)
def my_tasks(
    request: Request,
    overdue_only: bool = Query(False),
    due_this_week: bool = Query(False),
    project_id: int | None = Query(None),
    current_user: User = Depends(require_permission("projects.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    q = (
        db.query(ProjectTask, Project)
        .join(Project, ProjectTask.project_id == Project.id)
        .options(joinedload(Project.contact))
        .filter(
            Project.company_id == company.id,
            ProjectTask.assigned_to_id == current_user.id,
            ProjectTask.status.in_(OPEN_TASK_STATUSES),
            _accessible_project_filter(current_user, db, company.id),
        )
    )
    if project_id:
        q = q.filter(Project.id == project_id)
    if overdue_only:
        q = q.filter(ProjectTask.due_date.isnot(None), ProjectTask.due_date < _utcnow())
    if due_this_week:
        from datetime import timedelta

        start = _today_start()
        end = start + timedelta(days=7)
        q = q.filter(ProjectTask.due_date.isnot(None), ProjectTask.due_date >= start, ProjectTask.due_date <= end)

    rows = q.order_by(ProjectTask.due_date.asc().nullslast(), ProjectTask.priority.desc()).all()
    items = [
        ProjectMyTaskRow(
            id=task.id,
            title=task.title,
            status=task.status,
            status_label=TASK_STATUS_LABELS.get(task.status, task.status),
            priority=task.priority,
            priority_label=PROJECT_PRIORITY_LABELS.get(task.priority, task.priority),
            due_date=task.due_date,
            is_overdue=_is_task_overdue(task),
            stage_key=task.stage_key,
            stage_label=PROJECT_STAGE_LABELS.get(task.stage_key, task.stage_key),
            project_id=project.id,
            project_name=project.name,
            project_number=project.project_number,
            client_name=project.contact.name if project.contact else None,
            project_deadline=project.deadline,
        )
        for task, project in rows
    ]
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="my_tasks_viewed",
        details=f"My Tasks viewed ({len(items)} open tasks)",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return ProjectMyTasksResponse(items=items, total=len(items))


@router.get("/contacts/{contact_id}/summary", response_model=ProjectContactSummaryResponse)
def contact_project_summary(
    contact_id: int,
    current_user: User = Depends(require_permission("projects.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.company_id == company.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    projects = (
        db.query(Project)
        .options(joinedload(Project.contact), joinedload(Project.project_manager), joinedload(Project.tasks))
        .filter(
            Project.company_id == company.id,
            Project.contact_id == contact_id,
            _accessible_project_filter(current_user, db, company.id),
        )
        .order_by(Project.deadline.asc().nullslast())
        .all()
    )
    active = [p for p in projects if p.status == "active"]
    nearest = next((p.deadline for p in active if p.deadline), None)
    return ProjectContactSummaryResponse(
        contact_id=contact_id,
        active_project_count=len(active),
        nearest_deadline=nearest,
        projects=[_project_list_row(p) for p in projects[:10]],
    )


@router.get("", response_model=ProjectListResponse)
def list_projects(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    manager_id: int | None = Query(None),
    contact_id: int | None = Query(None),
    deal_id: int | None = Query(None),
    sales_order_id: int | None = Query(None),
    overdue_only: bool = Query(False),
    mine: bool = Query(False),
    sort: str = Query("deadline"),
    current_user: User = Depends(require_permission("projects.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    q = (
        db.query(Project)
        .options(
            joinedload(Project.contact),
            joinedload(Project.project_manager),
            joinedload(Project.tasks),
        )
        .filter(_accessible_project_filter(current_user, db, company.id))
    )
    if status:
        _validate_project_status(status)
        q = q.filter(Project.status == status)
    else:
        q = q.filter(Project.status != "cancelled")
    if manager_id:
        q = q.filter(Project.project_manager_id == manager_id)
    if contact_id:
        q = q.filter(Project.contact_id == contact_id)
    if deal_id:
        q = q.filter(Project.deal_id == deal_id)
    if sales_order_id:
        q = q.filter(Project.sales_order_id == sales_order_id)
    if mine:
        q = q.filter(Project.project_manager_id == current_user.id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                Project.name.ilike(term),
                Project.project_number.ilike(term),
                Project.description.ilike(term),
            )
        )
    projects = q.all()
    rows = [_project_list_row(p) for p in projects]
    if overdue_only:
        rows = [r for r in rows if r.is_overdue or r.overdue_task_count > 0]

    if sort == "name":
        rows.sort(key=lambda r: r.name.lower())
    elif sort == "progress":
        rows.sort(key=lambda r: r.progress_percent)
    elif sort == "updated":
        rows.sort(key=lambda r: r.updated_at or _utcnow(), reverse=True)
    else:
        rows.sort(key=lambda r: (r.deadline is None, r.deadline or _utcnow()))

    total = len(rows)
    start = (page - 1) * limit
    page_rows = rows[start : start + limit]

    all_accessible = (
        db.query(Project)
        .options(joinedload(Project.tasks))
        .filter(_accessible_project_filter(current_user, db, company.id))
        .all()
    )
    now = _utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    my_open = (
        db.query(func.count(ProjectTask.id))
        .join(Project)
        .filter(
            Project.company_id == company.id,
            ProjectTask.assigned_to_id == current_user.id,
            ProjectTask.status.in_(OPEN_TASK_STATUSES),
            _accessible_project_filter(current_user, db, company.id),
        )
        .scalar()
        or 0
    )
    kpis = ProjectIndexKpis(
        active_projects=sum(1 for p in all_accessible if p.status == "active"),
        overdue_projects=sum(1 for p in all_accessible if _is_project_overdue(p)),
        my_open_tasks=my_open,
        completed_this_month=sum(
            1 for p in all_accessible if p.status == "completed" and p.completed_at and p.completed_at >= month_start
        ),
    )

    return ProjectListResponse(items=page_rows, total=total, page=page, limit=limit, kpis=kpis)


@router.post("", response_model=ProjectDetailResponse)
def create_project(
    payload: ProjectCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("projects.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    _validate_project_type(payload.project_type)
    _validate_project_status(payload.status)
    _validate_priority(payload.priority)
    _validate_dates(payload.start_date, payload.deadline)
    _validate_staff(db, payload.project_manager_id, company.id, "Project manager")
    if payload.project_type == "client" and not payload.contact_id:
        raise HTTPException(status_code=400, detail="Client projects require a contact")
    _validate_links(db, company.id, payload.contact_id, payload.deal_id, payload.sales_order_id)

    project_number = payload.project_number.strip() if payload.project_number else _generate_project_number(db, company)
    if payload.project_number:
        existing = (
            db.query(Project)
            .filter(Project.company_id == company.id, Project.project_number == project_number)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Project number already exists")

    project = Project(
        company_id=company.id,
        project_number=project_number,
        name=payload.name.strip(),
        description=payload.description,
        project_type=payload.project_type,
        status=payload.status,
        priority=payload.priority,
        contact_id=payload.contact_id,
        deal_id=payload.deal_id,
        sales_order_id=payload.sales_order_id,
        project_manager_id=payload.project_manager_id,
        created_by_id=current_user.id,
        start_date=payload.start_date,
        deadline=payload.deadline,
    )
    db.add(project)
    db.flush()

    db.add(
        ProjectMember(
            project_id=project.id,
            user_id=payload.project_manager_id,
            role="manager",
            added_by_id=current_user.id,
        )
    )
    db.commit()
    db.refresh(project)
    project = _get_project(db, project.id, company.id)

    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_created",
        details=f"Created project {project.project_number or project.name}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _project_detail_resp(project)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: int,
    current_user: User = Depends(require_permission("projects.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)
    return _project_detail_resp(project)


@router.put("/{project_id}", response_model=ProjectDetailResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("projects.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)

    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.description is not None:
        project.description = payload.description
    if payload.project_type is not None:
        _validate_project_type(payload.project_type)
        project.project_type = payload.project_type
    if payload.priority is not None:
        _validate_priority(payload.priority)
        project.priority = payload.priority
    if payload.contact_id is not None:
        project.contact_id = payload.contact_id
    if payload.deal_id is not None:
        project.deal_id = payload.deal_id
    if payload.sales_order_id is not None:
        project.sales_order_id = payload.sales_order_id
    if payload.project_manager_id is not None:
        _validate_staff(db, payload.project_manager_id, company.id, "Project manager")
        project.project_manager_id = payload.project_manager_id
    if payload.start_date is not None:
        project.start_date = payload.start_date
    if payload.deadline is not None:
        project.deadline = payload.deadline
    if payload.project_number is not None:
        num = payload.project_number.strip()
        existing = (
            db.query(Project)
            .filter(Project.company_id == company.id, Project.project_number == num, Project.id != project.id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Project number already exists")
        project.project_number = num

    if project.project_type == "client" and not project.contact_id:
        raise HTTPException(status_code=400, detail="Client projects require a contact")
    _validate_dates(project.start_date, project.deadline)
    _validate_links(db, company.id, project.contact_id, project.deal_id, project.sales_order_id)

    db.commit()
    project = _get_project(db, project.id, company.id)
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_updated",
        details=f"Updated project {project.project_number or project.name}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _project_detail_resp(project)


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    request: Request,
    current_user: User = Depends(require_permission("projects.delete")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)
    if project.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft projects can be deleted")
    label = project.project_number or project.name
    db.delete(project)
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_deleted",
        details=f"Deleted draft project {label}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"ok": True}


@router.post("/{project_id}/status", response_model=ProjectDetailResponse)
def change_project_status(
    project_id: int,
    payload: ProjectStatusChangeRequest,
    request: Request,
    current_user: User = Depends(require_permission("projects.close")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)
    _validate_project_status(payload.status)

    if project.status in TERMINAL_PROJECT_STATUSES and payload.status != project.status:
        if not _can_edit_project(current_user, db):
            raise HTTPException(status_code=400, detail="Completed or cancelled projects cannot be reopened")

    if payload.status == "completed":
        open_tasks = [t for t in project.tasks if t.status in OPEN_TASK_STATUSES]
        if open_tasks:
            pass  # Phase 1: allow completion with open tasks

    project.status = payload.status
    if payload.status == "completed":
        project.completed_at = _utcnow()
    elif payload.status == "active" and project.completed_at:
        project.completed_at = None

    db.commit()
    project = _get_project(db, project.id, company.id)
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_status_changed",
        details=f"Project {project.project_number or project.name} status -> {payload.status}"
        + (f" ({payload.reason})" if payload.reason else ""),
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _project_detail_resp(project)


@router.post("/{project_id}/members", response_model=ProjectDetailResponse)
def add_project_member(
    project_id: int,
    payload: ProjectMemberAddRequest,
    request: Request,
    current_user: User = Depends(require_permission("projects.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)
    _validate_member_role(payload.role)
    _validate_staff(db, payload.user_id, company.id)

    existing = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id, ProjectMember.user_id == payload.user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User is already a project member")

    db.add(
        ProjectMember(
            project_id=project.id,
            user_id=payload.user_id,
            role=payload.role,
            added_by_id=current_user.id,
        )
    )
    db.commit()
    project = _get_project(db, project.id, company.id)
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_member_added",
        details=f"Added member to project {project.project_number or project.name}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _project_detail_resp(project)


@router.delete("/{project_id}/members/{user_id}", response_model=ProjectDetailResponse)
def remove_project_member(
    project_id: int,
    user_id: int,
    request: Request,
    current_user: User = Depends(require_permission("projects.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)

    if user_id == project.project_manager_id:
        raise HTTPException(status_code=400, detail="Cannot remove the project manager; reassign manager first")

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id, ProjectMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()
    project = _get_project(db, project.id, company.id)
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_member_removed",
        details=f"Removed member from project {project.project_number or project.name}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _project_detail_resp(project)


@router.post("/{project_id}/tasks", response_model=ProjectDetailResponse)
def create_task(
    project_id: int,
    payload: ProjectTaskCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("projects.manage_tasks")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)
    if not _can_manage_tasks(current_user, db, project):
        raise HTTPException(status_code=403, detail="You cannot manage tasks on this project")
    if project.status in TERMINAL_PROJECT_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot add tasks to a closed project")

    _validate_stage(payload.stage_key)
    _validate_task_status(payload.status)
    _validate_priority(payload.priority)
    _validate_staff(db, payload.assigned_to_id, company.id, "Assignee")

    due_date = payload.due_date or project.deadline
    task = ProjectTask(
        project_id=project.id,
        stage_key=payload.stage_key,
        title=payload.title.strip(),
        description=payload.description,
        assigned_to_id=payload.assigned_to_id,
        created_by_id=current_user.id,
        status=payload.status,
        priority=payload.priority,
        due_date=due_date,
        sort_order=payload.sort_order,
        blocked_reason=payload.blocked_reason,
    )
    if payload.status == "done":
        task.completed_at = _utcnow()
    db.add(task)
    if payload.assigned_to_id:
        _ensure_assignee_is_member(db, project, payload.assigned_to_id, current_user.id)
    db.commit()
    project = _get_project(db, project.id, company.id)
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_task_created",
        details=f"Created task on project {project.project_number or project.name}: {task.title}",
        ip_address=get_client_ip(request),
    )
    if payload.assigned_to_id:
        log_activity(
            db,
            user_id=current_user.id,
            email=current_user.email,
            action="project_task_assigned",
            details=f"Assigned task '{task.title}' on project {project.project_number or project.name}",
            ip_address=get_client_ip(request),
        )
    db.commit()
    return _project_detail_resp(project)


def _task_edit_level(user: User, db: Session, project: Project, task: ProjectTask) -> str:
    if project.status in LOCKED_TASK_PROJECT_STATUSES and not _can_edit_project(user, db):
        raise HTTPException(status_code=400, detail="Project is locked; task edits require manager permission")
    if _user_has_view_all(user, db) or _can_edit_project(user, db) or project.project_manager_id == user.id:
        return "full"
    if task.assigned_to_id == user.id and role_has_permission(db, user.role, "projects.manage_tasks"):
        return "limited"
    raise HTTPException(status_code=403, detail="You cannot edit this task")


@router.put("/{project_id}/tasks/{task_id}", response_model=ProjectDetailResponse)
def update_task(
    project_id: int,
    task_id: int,
    payload: ProjectTaskUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("projects.manage_tasks")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)

    task = db.query(ProjectTask).filter(ProjectTask.id == task_id, ProjectTask.project_id == project.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    edit_level = _task_edit_level(current_user, db, project, task)
    old_assignee_id = task.assigned_to_id
    old_status = task.status

    if payload.title is not None and edit_level == "full":
        task.title = payload.title.strip()
    if payload.description is not None and edit_level == "full":
        task.description = payload.description
    if payload.stage_key is not None and edit_level == "full":
        _validate_stage(payload.stage_key)
        task.stage_key = payload.stage_key
    if "assigned_to_id" in payload.model_fields_set and edit_level == "full":
        if payload.assigned_to_id is not None:
            _validate_staff(db, payload.assigned_to_id, company.id, "Assignee")
        task.assigned_to_id = payload.assigned_to_id
        if payload.assigned_to_id:
            _ensure_assignee_is_member(db, project, payload.assigned_to_id, current_user.id)
    if payload.priority is not None and edit_level == "full":
        _validate_priority(payload.priority)
        task.priority = payload.priority
    if payload.due_date is not None and edit_level == "full":
        task.due_date = payload.due_date
    if payload.sort_order is not None and edit_level == "full":
        task.sort_order = payload.sort_order
    if payload.blocked_reason is not None:
        task.blocked_reason = payload.blocked_reason
    if payload.status is not None:
        _validate_task_status(payload.status)
        task.status = payload.status
        if payload.status == "done" and old_status != "done":
            task.completed_at = _utcnow()
        elif payload.status != "done":
            task.completed_at = None

    db.commit()
    project = _get_project(db, project.id, company.id)

    if payload.status == "done" and old_status != "done":
        log_activity(
            db,
            user_id=current_user.id,
            email=current_user.email,
            action="project_task_completed",
            details=f"Completed task '{task.title}' on project {project.project_number or project.name}",
            ip_address=get_client_ip(request),
        )
    elif payload.status is not None and payload.status != old_status:
        log_activity(
            db,
            user_id=current_user.id,
            email=current_user.email,
            action="project_task_status_changed",
            details=f"Task '{task.title}' status {old_status} -> {payload.status} on project {project.project_number or project.name}",
            ip_address=get_client_ip(request),
        )
    elif "assigned_to_id" in payload.model_fields_set and task.assigned_to_id != old_assignee_id:
        log_activity(
            db,
            user_id=current_user.id,
            email=current_user.email,
            action="project_task_assigned",
            details=f"Reassigned task '{task.title}' on project {project.project_number or project.name}",
            ip_address=get_client_ip(request),
        )
    else:
        log_activity(
            db,
            user_id=current_user.id,
            email=current_user.email,
            action="project_task_updated",
            details=f"Updated task on project {project.project_number or project.name}: {task.title}",
            ip_address=get_client_ip(request),
        )
    db.commit()
    return _project_detail_resp(project)


@router.delete("/{project_id}/tasks/{task_id}", response_model=ProjectDetailResponse)
def delete_task(
    project_id: int,
    task_id: int,
    request: Request,
    current_user: User = Depends(require_permission("projects.manage_tasks")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, project_id, company.id)
    _ensure_project_access(db, current_user, project)
    if not _can_manage_tasks(current_user, db, project):
        raise HTTPException(status_code=403, detail="You cannot manage tasks on this project")
    if project.status in LOCKED_TASK_PROJECT_STATUSES and not _can_edit_project(current_user, db):
        raise HTTPException(status_code=400, detail="Project is locked")

    task = db.query(ProjectTask).filter(ProjectTask.id == task_id, ProjectTask.project_id == project.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    title = task.title
    db.delete(task)
    db.commit()
    project = _get_project(db, project.id, company.id)
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_task_deleted",
        details=f"Deleted task on project {project.project_number or project.name}: {title}",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _project_detail_resp(project)


@router.post("/export-log")
def log_project_export(
    payload: ProjectExportLogRequest,
    request: Request,
    current_user: User = Depends(require_permission("projects.export")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    project = _get_project(db, payload.project_id, company.id)
    _ensure_project_access(db, current_user, project)
    log_activity(
        db,
        user_id=current_user.id,
        email=current_user.email,
        action="project_exported",
        details=f"Exported tasks for project {project.project_number or project.name} ({payload.row_count} rows)",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"ok": True}
