"""Field Service API."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from field_service_config import (
    DEFAULT_NOTIFY_ROLES,
    DEFAULT_ORDER_PREFIX,
    DEFAULT_SLA_HOURS,
    FSO_PRIORITIES,
    FSO_STATUS_TRANSITIONS,
    FSO_TYPES,
    OPEN_FSO_STATUSES,
    PARTS_ISSUE_STATUSES,
    URGENT_UNASSIGNED_HOURS,
)
from field_service_schemas import (
    FieldServiceDashboardResponse,
    FieldServiceSettingsResponse,
    FieldServiceSettingsUpdateRequest,
    FsoAssignRequest,
    FsoCompleteRequest,
    FsoCreateRequest,
    FsoIssuePartsRequest,
    FsoListItem,
    FsoListResponse,
    FsoPartLine,
    FsoResponse,
    FsoStatusUpdateRequest,
    FsoUpdateRequest,
    ScheduleResponse,
)
from models import (
    Company,
    Contact,
    FieldServiceOrder,
    FieldServiceOrderPart,
    FieldServiceSettings,
    Notification,
    Product,
    User,
)
from routers.inventory_router import _apply_movement
from services.notification_service import notify_role

router = APIRouter(prefix="/field-service", tags=["field-service"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)




def _get_settings(db: Session, company: Company) -> FieldServiceSettings:
    settings = db.query(FieldServiceSettings).filter(FieldServiceSettings.company_id == company.id).first()
    if settings:
        return settings
    settings = FieldServiceSettings(
        company_id=company.id,
        is_enabled=True,
        notify_roles_json=DEFAULT_NOTIFY_ROLES,
        default_sla_hours=DEFAULT_SLA_HOURS,
        order_prefix=DEFAULT_ORDER_PREFIX,
    )
    db.add(settings)
    db.flush()
    return settings


def _require_enabled(settings: FieldServiceSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=400, detail="Field Service module is not enabled")


def _settings_response(settings: FieldServiceSettings) -> FieldServiceSettingsResponse:
    return FieldServiceSettingsResponse(
        is_enabled=settings.is_enabled,
        order_prefix=settings.order_prefix or DEFAULT_ORDER_PREFIX,
        default_sla_hours=int(settings.default_sla_hours or DEFAULT_SLA_HOURS),
        auto_deduct_parts=bool(settings.auto_deduct_parts),
        allow_negative_parts=bool(settings.allow_negative_parts),
        notify_roles_json=settings.notify_roles_json or [],
        service_types_json=settings.service_types_json or [],
    )


def _contact_address(contact: Contact) -> str:
    parts = [contact.address_line1, contact.address_line2, contact.city, contact.state, contact.pincode]
    return ", ".join(p for p in parts if p)


def _generate_order_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    pattern = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(FieldServiceOrder.company_id == company_id, FieldServiceOrder.order_number.like(pattern))
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def _sla_breached(order: FieldServiceOrder) -> bool:
    if not order.sla_due_at or order.status in ("completed", "cancelled"):
        return False
    return order.sla_due_at < _utcnow()


def _fso_list_item(order: FieldServiceOrder) -> FsoListItem:
    return FsoListItem(
        id=order.id,
        order_number=order.order_number,
        contact_id=order.contact_id,
        contact_name=order.contact.name if order.contact else None,
        type=order.type,
        priority=order.priority,
        status=order.status,
        title=order.title,
        site_address=order.site_address,
        scheduled_start=order.scheduled_start,
        scheduled_end=order.scheduled_end,
        assigned_to_id=order.assigned_to_id,
        assigned_to_name=order.assigned_to.name if order.assigned_to else None,
        sla_due_at=order.sla_due_at,
        sla_breached=_sla_breached(order),
    )


def _fso_response(order: FieldServiceOrder) -> FsoResponse:
    parts = []
    for line in order.parts or []:
        product = line.product
        parts.append(
            FsoPartLine(
                id=line.id,
                product_id=line.product_id,
                product_name=product.name if product else f"Product #{line.product_id}",
                quantity=_float(line.quantity),
                unit=product.unit if product else None,
                issued_at=line.issued_at,
                issued_by_name=line.issued_by.name if line.issued_by else None,
            )
        )
    return FsoResponse(
        id=order.id,
        order_number=order.order_number,
        contact_id=order.contact_id,
        contact_name=order.contact.name if order.contact else None,
        type=order.type,
        priority=order.priority,
        status=order.status,
        title=order.title,
        description=order.description,
        site_address=order.site_address,
        site_contact_name=order.site_contact_name,
        site_contact_phone=order.site_contact_phone,
        site_notes=order.site_notes,
        scheduled_start=order.scheduled_start,
        scheduled_end=order.scheduled_end,
        dispatched_at=order.dispatched_at,
        arrived_at=order.arrived_at,
        completed_at=order.completed_at,
        resolution_notes=order.resolution_notes,
        root_cause=order.root_cause,
        assigned_to_id=order.assigned_to_id,
        assigned_to_name=order.assigned_to.name if order.assigned_to else None,
        sla_due_at=order.sla_due_at,
        sla_breached=_sla_breached(order),
        parts=parts,
    )


def _get_fso(db: Session, company_id: int, order_id: int) -> FieldServiceOrder:
    order = (
        db.query(FieldServiceOrder)
        .options(
            joinedload(FieldServiceOrder.contact),
            joinedload(FieldServiceOrder.assigned_to),
            joinedload(FieldServiceOrder.parts).joinedload(FieldServiceOrderPart.product),
            joinedload(FieldServiceOrder.parts).joinedload(FieldServiceOrderPart.issued_by),
        )
        .filter(FieldServiceOrder.id == order_id, FieldServiceOrder.company_id == company_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Field service order not found")
    return order


def _get_contact(db: Session, company_id: int, contact_id: int) -> Contact:
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.company_id == company_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


def _issue_parts_stock(
    db: Session,
    product: Product,
    user: User,
    qty: float,
    order_number: str,
    allow_negative: bool,
) -> int | None:
    if not product.inventory_tracked:
        return None
    movement = _apply_movement(
        db,
        product,
        user,
        "sale",
        qty,
        _float(product.unit_valuation),
        _utcnow(),
        reason="internal_consumption",
        notes=f"Field service parts for {order_number}",
        reference_number=order_number,
        reference_type="field_service_order",
        source_module="field_service",
        allow_negative=allow_negative,
    )
    return movement.id


def _sync_fso_alerts(db: Session, company: Company, settings: FieldServiceSettings) -> None:
    if not settings.is_enabled:
        return
    roles = settings.notify_roles_json or DEFAULT_NOTIFY_ROLES
    now = _utcnow()
    today = now.date()

    urgent_cutoff = now - timedelta(hours=URGENT_UNASSIGNED_HOURS)
    urgent_unassigned = (
        db.query(FieldServiceOrder)
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.assigned_to_id.is_(None),
            FieldServiceOrder.priority.in_(("urgent", "high")),
            FieldServiceOrder.status.in_(OPEN_FSO_STATUSES),
            FieldServiceOrder.created_at < urgent_cutoff,
        )
        .all()
    )
    for order in urgent_unassigned:
        link = f"/field-service/orders/{order.id}"
        title = f"Urgent FSO unassigned: {order.order_number}"
        if not _notification_exists_today(db, company.id, title, link, today):
            for role in roles:
                notify_role(
                    db,
                    company_id=company.id,
                    role=role,
                    category="field_service",
                    title=title,
                    message=order.title,
                    link_path=link,
                )

    sla_breached = (
        db.query(FieldServiceOrder)
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.sla_due_at.isnot(None),
            FieldServiceOrder.sla_due_at < now,
            FieldServiceOrder.status.notin_(("completed", "cancelled")),
        )
        .all()
    )
    for order in sla_breached:
        link = f"/field-service/orders/{order.id}"
        title = f"SLA breached: {order.order_number}"
        if not _notification_exists_today(db, company.id, title, link, today):
            for role in roles:
                notify_role(
                    db,
                    company_id=company.id,
                    role=role,
                    category="field_service",
                    title=title,
                    message=f"Due {order.sla_due_at}",
                    link_path=link,
                )


def _notification_exists_today(db: Session, company_id: int, title: str, link: str, today: date) -> bool:
    return (
        db.query(Notification.id)
        .filter(
            Notification.company_id == company_id,
            Notification.category == "field_service",
            Notification.title == title,
            Notification.link_path == link,
            Notification.created_at >= datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
        )
        .first()
        is not None
    )


@router.get("/settings", response_model=FieldServiceSettingsResponse)
def get_settings_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.view")),
):
    company = get_current_company(db, user)
    return _settings_response(_get_settings(db, company))


@router.put("/settings", response_model=FieldServiceSettingsResponse)
def update_settings(
    body: FieldServiceSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.manage_settings")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    log_activity(db, "field_service_settings_updated", user_id=user.id, details={"company_id": company.id}, ip_address=get_client_ip(request))
    return _settings_response(settings)


@router.get("/dashboard", response_model=FieldServiceDashboardResponse)
def field_service_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.view")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    _sync_fso_alerts(db, company, settings)

    now = _utcnow()
    today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    today_end = datetime.combine(now.date(), datetime.max.time(), tzinfo=timezone.utc)
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    open_count = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(FieldServiceOrder.company_id == company.id, FieldServiceOrder.status.in_(OPEN_FSO_STATUSES))
        .scalar()
    )
    unassigned = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.assigned_to_id.is_(None),
            FieldServiceOrder.status.in_(OPEN_FSO_STATUSES),
        )
        .scalar()
    )
    todays = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.scheduled_start.isnot(None),
            FieldServiceOrder.scheduled_start >= today_start,
            FieldServiceOrder.scheduled_start <= today_end,
            FieldServiceOrder.status.notin_(("completed", "cancelled")),
        )
        .scalar()
    )
    sla_breached_count = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.sla_due_at.isnot(None),
            FieldServiceOrder.sla_due_at < now,
            FieldServiceOrder.status.notin_(("completed", "cancelled")),
        )
        .scalar()
    )
    completions_7d = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.status == "completed",
            FieldServiceOrder.completed_at >= since_7d,
        )
        .scalar()
    )
    completions_30d = (
        db.query(func.count(FieldServiceOrder.id))
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.status == "completed",
            FieldServiceOrder.completed_at >= since_30d,
        )
        .scalar()
    )

    unassigned_q = (
        db.query(FieldServiceOrder)
        .options(joinedload(FieldServiceOrder.contact), joinedload(FieldServiceOrder.assigned_to))
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.assigned_to_id.is_(None),
            FieldServiceOrder.status.in_(OPEN_FSO_STATUSES),
        )
        .order_by(FieldServiceOrder.priority.desc(), FieldServiceOrder.created_at)
        .limit(10)
        .all()
    )
    today_schedule = (
        db.query(FieldServiceOrder)
        .options(joinedload(FieldServiceOrder.contact), joinedload(FieldServiceOrder.assigned_to))
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.scheduled_start.isnot(None),
            FieldServiceOrder.scheduled_start >= today_start,
            FieldServiceOrder.scheduled_start <= today_end,
            FieldServiceOrder.status.notin_(("completed", "cancelled")),
        )
        .order_by(FieldServiceOrder.scheduled_start)
        .limit(15)
        .all()
    )
    sla_list = (
        db.query(FieldServiceOrder)
        .options(joinedload(FieldServiceOrder.contact), joinedload(FieldServiceOrder.assigned_to))
        .filter(
            FieldServiceOrder.company_id == company.id,
            FieldServiceOrder.sla_due_at.isnot(None),
            FieldServiceOrder.sla_due_at < now,
            FieldServiceOrder.status.notin_(("completed", "cancelled")),
        )
        .order_by(FieldServiceOrder.sla_due_at)
        .limit(10)
        .all()
    )
    recent = (
        db.query(FieldServiceOrder)
        .options(joinedload(FieldServiceOrder.contact), joinedload(FieldServiceOrder.assigned_to))
        .filter(FieldServiceOrder.company_id == company.id, FieldServiceOrder.status == "completed")
        .order_by(FieldServiceOrder.completed_at.desc())
        .limit(10)
        .all()
    )

    db.commit()

    return FieldServiceDashboardResponse(
        open_orders=int(open_count or 0),
        unassigned=int(unassigned or 0),
        todays_visits=int(todays or 0),
        sla_breached=int(sla_breached_count or 0),
        completions_7d=int(completions_7d or 0),
        completions_30d=int(completions_30d or 0),
        unassigned_queue=[_fso_list_item(o) for o in unassigned_q],
        todays_schedule=[_fso_list_item(o) for o in today_schedule],
        sla_breached_list=[_fso_list_item(o) for o in sla_list],
        recent_completions=[_fso_list_item(o) for o in recent],
    )


@router.get("/orders", response_model=FsoListResponse)
def list_orders(
    type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    contact_id: int | None = None,
    assigned_to_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.view")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    q = (
        db.query(FieldServiceOrder)
        .options(joinedload(FieldServiceOrder.contact), joinedload(FieldServiceOrder.assigned_to))
        .filter(FieldServiceOrder.company_id == company.id)
    )
    if type:
        q = q.filter(FieldServiceOrder.type == type)
    if status:
        q = q.filter(FieldServiceOrder.status == status)
    if priority:
        q = q.filter(FieldServiceOrder.priority == priority)
    if contact_id:
        q = q.filter(FieldServiceOrder.contact_id == contact_id)
    if assigned_to_id:
        q = q.filter(FieldServiceOrder.assigned_to_id == assigned_to_id)
    rows = q.order_by(FieldServiceOrder.created_at.desc()).all()
    return FsoListResponse(items=[_fso_list_item(o) for o in rows], total=len(rows))


@router.post("/orders", response_model=FsoResponse)
def create_order(
    body: FsoCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.create")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    if body.type not in FSO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid service type")
    if body.priority not in FSO_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority")

    contact = _get_contact(db, company.id, body.contact_id)
    site_address = (body.site_address or "").strip() or _contact_address(contact)
    now = _utcnow()
    sla_hours = int(settings.default_sla_hours or DEFAULT_SLA_HOURS)
    prefix = settings.order_prefix or DEFAULT_ORDER_PREFIX

    order = FieldServiceOrder(
        company_id=company.id,
        order_number=_generate_order_number(db, company.id, prefix),
        contact_id=contact.id,
        type=body.type,
        priority=body.priority,
        status="draft",
        title=body.title.strip(),
        description=body.description,
        site_address=site_address or None,
        site_contact_name=body.site_contact_name or contact.name,
        site_contact_phone=body.site_contact_phone or contact.phone,
        site_notes=body.site_notes,
        sla_due_at=now + timedelta(hours=sla_hours),
        created_by_id=user.id,
    )
    db.add(order)
    db.commit()
    order = _get_fso(db, company.id, order.id)
    log_activity(
        db,
        "field_service_order_created",
        user_id=user.id,
        details={"order_id": order.id, "order_number": order.order_number},
        ip_address=get_client_ip(request),
    )
    return _fso_response(order)


@router.get("/orders/{order_id}", response_model=FsoResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.view")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    return _fso_response(_get_fso(db, company.id, order_id))


@router.put("/orders/{order_id}", response_model=FsoResponse)
def update_order(
    order_id: int,
    body: FsoUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.create")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    order = _get_fso(db, company.id, order_id)
    if order.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Cannot edit completed or cancelled orders")
    data = body.model_dump(exclude_unset=True)
    if "type" in data and data["type"] not in FSO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid service type")
    if "priority" in data and data["priority"] not in FSO_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority")
    for key, value in data.items():
        setattr(order, key, value)
    db.commit()
    order = _get_fso(db, company.id, order_id)
    log_activity(db, "field_service_order_updated", user_id=user.id, details={"order_id": order.id}, ip_address=get_client_ip(request))
    return _fso_response(order)


@router.put("/orders/{order_id}/assign", response_model=FsoResponse)
def assign_order(
    order_id: int,
    body: FsoAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.dispatch")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    order = _get_fso(db, company.id, order_id)
    if order.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Cannot assign completed or cancelled orders")

    tech = db.query(User).filter(User.id == body.assigned_to_id, User.company_id == company.id).first()
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found")

    if not (order.site_address or "").strip():
        raise HTTPException(status_code=400, detail="Site address is required before scheduling")

    scheduled_end = body.scheduled_end or body.scheduled_start + timedelta(hours=4)
    if scheduled_end < body.scheduled_start:
        raise HTTPException(status_code=400, detail="Scheduled end must be after start")

    order.assigned_to_id = body.assigned_to_id
    order.scheduled_start = body.scheduled_start
    order.scheduled_end = scheduled_end
    order.status = "scheduled"
    order.dispatched_at = None
    order.arrived_at = None

    db.commit()
    order = _get_fso(db, company.id, order_id)
    log_activity(
        db,
        "field_service_order_assigned",
        user_id=user.id,
        details={"order_id": order.id, "assigned_to_id": body.assigned_to_id},
        ip_address=get_client_ip(request),
    )
    return _fso_response(order)


@router.put("/orders/{order_id}/reschedule", response_model=FsoResponse)
def reschedule_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.dispatch")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    order = _get_fso(db, company.id, order_id)
    if order.status not in ("scheduled", "dispatched"):
        raise HTTPException(status_code=400, detail="Only scheduled or dispatched orders can be rescheduled")
    order.status = "rescheduled"
    order.dispatched_at = None
    db.commit()
    order = _get_fso(db, company.id, order_id)
    log_activity(db, "field_service_order_rescheduled", user_id=user.id, details={"order_id": order.id}, ip_address=get_client_ip(request))
    return _fso_response(order)


@router.put("/orders/{order_id}/status", response_model=FsoResponse)
def update_order_status(
    order_id: int,
    body: FsoStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.execute")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    order = _get_fso(db, company.id, order_id)
    new_status = body.status
    if new_status not in FSO_STATUS_TRANSITIONS:
        raise HTTPException(status_code=400, detail="Invalid status")
    if new_status == "cancelled":
        raise HTTPException(status_code=400, detail="Use cancel endpoint to cancel orders")
    allowed = FSO_STATUS_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {order.status} to {new_status}")

    if new_status in ("scheduled", "dispatched", "in_progress") and not order.site_address:
        raise HTTPException(status_code=400, detail="Site address is required")

    old_status = order.status
    order.status = new_status
    now = _utcnow()
    if new_status == "dispatched" and not order.dispatched_at:
        order.dispatched_at = now
    if new_status == "in_progress":
        if not order.arrived_at:
            order.arrived_at = now
        if not order.dispatched_at:
            order.dispatched_at = now

    db.commit()
    order = _get_fso(db, company.id, order_id)
    log_activity(
        db,
        "field_service_order_status_changed",
        user_id=user.id,
        details={"order_id": order.id, "from": old_status, "to": new_status},
        ip_address=get_client_ip(request),
    )
    return _fso_response(order)


@router.put("/orders/{order_id}/cancel", response_model=FsoResponse)
def cancel_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.cancel")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    order = _get_fso(db, company.id, order_id)
    if order.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Order already closed")
    order.status = "cancelled"
    db.commit()
    order = _get_fso(db, company.id, order_id)
    log_activity(db, "field_service_order_cancelled", user_id=user.id, details={"order_id": order.id}, ip_address=get_client_ip(request))
    return _fso_response(order)


@router.post("/orders/{order_id}/parts", response_model=FsoResponse)
def issue_parts(
    order_id: int,
    body: FsoIssuePartsRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.issue_parts")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    order = _get_fso(db, company.id, order_id)
    if order.status not in PARTS_ISSUE_STATUSES:
        raise HTTPException(status_code=400, detail="Parts can only be issued to active service orders")

    product = db.query(Product).filter(Product.id == body.product_id, Product.company_id == company.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_spare_part and not product.inventory_tracked:
        raise HTTPException(status_code=400, detail="Product is not flagged as spare part or inventory-tracked")

    qty = _float(body.quantity)
    movement_id = None
    if settings.auto_deduct_parts and product.inventory_tracked:
        on_hand = _float(product.on_hand_quantity)
        if on_hand < qty and not settings.allow_negative_parts:
            raise HTTPException(status_code=400, detail="Insufficient stock for this part")
        movement_id = _issue_parts_stock(
            db,
            product,
            user,
            qty,
            order.order_number,
            allow_negative=bool(settings.allow_negative_parts),
        )

    part = FieldServiceOrderPart(
        field_service_order_id=order.id,
        product_id=product.id,
        quantity=qty,
        stock_movement_id=movement_id,
        issued_by_id=user.id,
        issued_at=_utcnow(),
    )
    db.add(part)
    db.commit()
    order = _get_fso(db, company.id, order_id)
    log_activity(
        db,
        "field_service_parts_issued",
        user_id=user.id,
        details={"order_id": order.id, "product_id": product.id, "quantity": qty},
        ip_address=get_client_ip(request),
    )
    return _fso_response(order)


@router.post("/orders/{order_id}/complete", response_model=FsoResponse)
def complete_order(
    order_id: int,
    body: FsoCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.execute")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)
    order = _get_fso(db, company.id, order_id)
    if order.status not in ("in_progress", "waiting_parts", "dispatched", "scheduled"):
        raise HTTPException(status_code=400, detail="Order cannot be completed from current status")

    now = _utcnow()
    order.status = "completed"
    order.completed_at = now
    order.resolution_notes = body.resolution_notes.strip()
    order.root_cause = body.root_cause
    if not order.arrived_at:
        order.arrived_at = now

    db.commit()
    order = _get_fso(db, company.id, order_id)
    log_activity(
        db,
        "field_service_order_completed",
        user_id=user.id,
        details={"order_id": order.id},
        ip_address=get_client_ip(request),
    )
    log_activity(db, "fso_completed", user_id=user.id, details={"order_id": order.id}, ip_address=get_client_ip(request))
    return _fso_response(order)


@router.get("/schedule", response_model=ScheduleResponse)
def get_schedule(
    view: str = Query("today"),
    assigned_to_id: int | None = None,
    unassigned: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("field_service.view")),
):
    company = get_current_company(db, user)
    settings = _get_settings(db, company)
    _require_enabled(settings)

    now = _utcnow()
    today = now.date()
    if view == "week":
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=7)
    else:
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)

    q = (
        db.query(FieldServiceOrder)
        .options(joinedload(FieldServiceOrder.contact), joinedload(FieldServiceOrder.assigned_to))
        .filter(FieldServiceOrder.company_id == company.id)
    )
    if unassigned:
        q = q.filter(
            FieldServiceOrder.assigned_to_id.is_(None),
            FieldServiceOrder.status.in_(OPEN_FSO_STATUSES),
        )
    else:
        q = q.filter(
            FieldServiceOrder.scheduled_start.isnot(None),
            FieldServiceOrder.scheduled_start >= start,
            FieldServiceOrder.scheduled_start <= end,
            FieldServiceOrder.status.notin_(("completed", "cancelled")),
        )
    if assigned_to_id:
        q = q.filter(FieldServiceOrder.assigned_to_id == assigned_to_id)

    rows = q.order_by(FieldServiceOrder.scheduled_start.nullslast(), FieldServiceOrder.priority.desc()).all()
    return ScheduleResponse(items=[_fso_list_item(o) for o in rows], total=len(rows))
