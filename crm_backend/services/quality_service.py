"""Shared Quality Control business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from manufacturing_config import DEFAULT_CHECKLIST as MFG_DEFAULT_CHECKLIST
from models import (
    Company,
    CorrectiveAction,
    InspectionPoint,
    Product,
    PurchaseOrder,
    QualityAlert,
    QualityChecklistTemplate,
    QualityInspection,
    QualitySettings,
    User,
    WorkOrder,
)
from quality_config import (
    DEFAULT_CHECKLIST,
    DEFAULT_NOTIFY_ROLES,
    DEFAULT_OVERDUE_HOURS,
    DEFAULT_REPEAT_FAIL_THRESHOLD,
    SEED_INSPECTION_POINTS,
)
from services.notification_service import notify_role

WO_FINAL_CODE = "WO_FINAL"
INCOMING_GRN_CODE = "INCOMING_GRN"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _float(v) -> float:
    return float(v or 0)


def get_quality_settings(db: Session, company: Company) -> QualitySettings:
    settings = db.query(QualitySettings).filter(QualitySettings.company_id == company.id).first()
    if settings:
        return settings
    settings = QualitySettings(
        company_id=company.id,
        is_enabled=True,
        notify_roles_json=DEFAULT_NOTIFY_ROLES,
        alert_repeat_fail_threshold=DEFAULT_REPEAT_FAIL_THRESHOLD,
        alert_overdue_hours=DEFAULT_OVERDUE_HOURS,
    )
    db.add(settings)
    db.flush()
    return settings


def seed_inspection_points(db: Session, company_id: int) -> None:
    for row in SEED_INSPECTION_POINTS:
        exists = (
            db.query(InspectionPoint)
            .filter(InspectionPoint.company_id == company_id, InspectionPoint.code == row["code"])
            .first()
        )
        if not exists:
            db.add(InspectionPoint(company_id=company_id, **row))


def get_point_by_code(db: Session, company_id: int, code: str) -> InspectionPoint | None:
    return (
        db.query(InspectionPoint)
        .filter(InspectionPoint.company_id == company_id, InspectionPoint.code == code)
        .first()
    )


def generate_inspection_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    like = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(QualityInspection.id))
        .filter(
            QualityInspection.company_id == company_id,
            QualityInspection.inspection_number.like(like),
        )
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def generate_capa_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    like = f"{prefix}-{year}-%"
    count = (
        db.query(func.count(CorrectiveAction.id))
        .filter(
            CorrectiveAction.company_id == company_id,
            CorrectiveAction.capa_number.like(like),
        )
        .scalar()
    )
    return f"{prefix}-{year}-{int(count or 0) + 1:04d}"


def resolve_template(
    db: Session,
    company_id: int,
    inspection_point_id: int | None,
    product_id: int | None,
) -> QualityChecklistTemplate | None:
    if product_id and inspection_point_id:
        tmpl = (
            db.query(QualityChecklistTemplate)
            .filter(
                QualityChecklistTemplate.company_id == company_id,
                QualityChecklistTemplate.product_id == product_id,
                QualityChecklistTemplate.inspection_point_id == inspection_point_id,
                QualityChecklistTemplate.status == "active",
            )
            .order_by(QualityChecklistTemplate.id.desc())
            .first()
        )
        if tmpl:
            return tmpl
    if inspection_point_id:
        point = db.query(InspectionPoint).filter(InspectionPoint.id == inspection_point_id).first()
        if point and point.default_template_id:
            tmpl = db.query(QualityChecklistTemplate).filter(QualityChecklistTemplate.id == point.default_template_id).first()
            if tmpl and tmpl.status == "active":
                return tmpl
        tmpl = (
            db.query(QualityChecklistTemplate)
            .filter(
                QualityChecklistTemplate.company_id == company_id,
                QualityChecklistTemplate.inspection_point_id == inspection_point_id,
                QualityChecklistTemplate.product_id.is_(None),
                QualityChecklistTemplate.status == "active",
            )
            .order_by(QualityChecklistTemplate.id.desc())
            .first()
        )
        if tmpl:
            return tmpl
    if product_id:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            if inspection_point_id:
                point = db.query(InspectionPoint).filter(InspectionPoint.id == inspection_point_id).first()
                if point and point.code == WO_FINAL_CODE and product.default_final_template_id:
                    return db.query(QualityChecklistTemplate).get(product.default_final_template_id)
                if point and point.code == INCOMING_GRN_CODE and product.default_incoming_template_id:
                    return db.query(QualityChecklistTemplate).get(product.default_incoming_template_id)
    return None


def checklist_from_template(template: QualityChecklistTemplate | None) -> list[dict]:
    if template and template.items_json:
        return [dict(item) for item in template.items_json]
    return [dict(item) for item in DEFAULT_CHECKLIST]


def evaluate_checklist(checklist_json: list[dict]) -> str:
    for item in checklist_json:
        if not item.get("required"):
            continue
        input_type = item.get("input_type", "pass_fail")
        if input_type == "number":
            value = item.get("value")
            if value is None or value == "":
                return "failed"
            spec = item.get("spec") or {}
            num = float(value)
            if spec.get("min") is not None and num < float(spec["min"]):
                item["passed"] = False
                return "failed"
            if spec.get("max") is not None and num > float(spec["max"]):
                item["passed"] = False
                return "failed"
            item["passed"] = True
        else:
            if item.get("passed") is not True:
                return "failed"
    return "passed"


def create_inspection(
    db: Session,
    company: Company,
    *,
    inspection_point_id: int,
    product_id: int | None = None,
    template_id: int | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    work_order_id: int | None = None,
    notes: str | None = None,
) -> QualityInspection:
    settings = get_quality_settings(db, company)
    template = None
    if template_id:
        template = (
            db.query(QualityChecklistTemplate)
            .filter(QualityChecklistTemplate.company_id == company.id, QualityChecklistTemplate.id == template_id)
            .first()
        )
    if not template:
        template = resolve_template(db, company.id, inspection_point_id, product_id)

    insp = QualityInspection(
        company_id=company.id,
        inspection_point_id=inspection_point_id,
        template_id=template.id if template else None,
        inspection_number=generate_inspection_number(db, company.id, settings.inspection_number_prefix),
        status="pending",
        checklist_json=checklist_from_template(template),
        notes=notes,
        reference_type=reference_type,
        reference_id=reference_id,
        work_order_id=work_order_id,
        product_id=product_id,
    )
    db.add(insp)
    db.flush()
    return insp


def create_wo_final_inspection(
    db: Session,
    company: Company,
    wo: WorkOrder,
    mfg_checklist: list | None = None,
) -> QualityInspection:
    existing = (
        db.query(QualityInspection)
        .filter(QualityInspection.work_order_id == wo.id, QualityInspection.status == "pending")
        .first()
    )
    if existing:
        return existing

    settings = get_quality_settings(db, company)
    if settings.is_enabled:
        seed_inspection_points(db, company.id)
        point = get_point_by_code(db, company.id, WO_FINAL_CODE)
        if point:
            insp = create_inspection(
                db,
                company,
                inspection_point_id=point.id,
                product_id=wo.product_id,
                reference_type="work_order",
                reference_id=wo.id,
                work_order_id=wo.id,
            )
            db.flush()
            return insp

    checklist = mfg_checklist or MFG_DEFAULT_CHECKLIST
    insp = QualityInspection(
        company_id=company.id,
        work_order_id=wo.id,
        inspection_number=generate_inspection_number(db, company.id, "QC"),
        status="pending",
        checklist_json=checklist,
        reference_type="work_order",
        reference_id=wo.id,
        product_id=wo.product_id,
    )
    db.add(insp)
    db.flush()
    return insp


def submit_inspection(
    db: Session,
    company: Company,
    insp: QualityInspection,
    user: User,
    checklist_json: list[dict],
    overall_notes: str | None = None,
    status_override: str | None = None,
) -> QualityInspection:
    if insp.status != "pending":
        raise ValueError("Inspection already submitted")

    for item in checklist_json:
        if item.get("input_type", "pass_fail") == "pass_fail" and item.get("required"):
            if item.get("passed") is None:
                raise ValueError(f"Required item not answered: {item.get('label', item.get('key'))}")

    result = status_override or evaluate_checklist(checklist_json)
    insp.checklist_json = checklist_json
    insp.notes = overall_notes
    insp.status = result
    insp.inspected_by_id = user.id
    insp.inspected_at = _utcnow()

    settings = get_quality_settings(db, company)
    if result == "failed" and settings.is_enabled:
        on_inspection_failed(db, company, insp, user)

    return insp


def waive_inspection(
    db: Session,
    company: Company,
    insp: QualityInspection,
    user: User,
    waiver_reason: str,
) -> QualityInspection:
    if insp.status not in ("failed", "pending"):
        raise ValueError("Only failed or pending inspections can be waived")
    insp.status = "waived"
    insp.waived_by_id = user.id
    insp.waiver_reason = waiver_reason
    if not insp.inspected_at:
        insp.inspected_at = _utcnow()
    if not insp.inspected_by_id:
        insp.inspected_by_id = user.id
    return insp


def create_incoming_po_inspection(
    db: Session,
    company: Company,
    po: PurchaseOrder,
    line_product_id: int | None,
) -> QualityInspection | None:
    settings = get_quality_settings(db, company)
    if not settings.is_enabled or not settings.default_incoming_required:
        return None
    seed_inspection_points(db, company.id)
    point = get_point_by_code(db, company.id, INCOMING_GRN_CODE)
    if not point or not point.is_active:
        return None
    return create_inspection(
        db,
        company,
        inspection_point_id=point.id,
        product_id=line_product_id,
        reference_type="purchase_order",
        reference_id=po.id,
    )


def wo_allows_fg_receipt(wo: WorkOrder, mfg_require_qc: bool) -> bool:
    if not mfg_require_qc:
        return True
    inspections = wo.quality_inspections or []
    if any(q.status in ("passed", "waived") for q in inspections):
        return True
    failed_final = [q for q in inspections if q.status == "failed"]
    if failed_final:
        return False
    return False


def wo_final_blocked_by_fail(wo: WorkOrder, settings: QualitySettings) -> bool:
    for insp in wo.quality_inspections or []:
        if insp.status != "failed":
            continue
        point = insp.inspection_point
        if point and point.code != WO_FINAL_CODE:
            continue
        block = point.block_on_fail if point else settings.block_on_fail_default
        if block:
            return True
    return False


def create_quality_alert(
    db: Session,
    company_id: int,
    *,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    inspection_id: int | None = None,
    capa_id: int | None = None,
    product_id: int | None = None,
) -> QualityAlert:
    if alert_type == "repeat_failure" and inspection_id and product_id:
        open_dup = (
            db.query(QualityAlert)
            .filter(
                QualityAlert.company_id == company_id,
                QualityAlert.alert_type == "repeat_failure",
                QualityAlert.product_id == product_id,
                QualityAlert.inspection_id == inspection_id,
                QualityAlert.status == "open",
            )
            .first()
        )
        if open_dup:
            return open_dup

    alert = QualityAlert(
        company_id=company_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        inspection_id=inspection_id,
        capa_id=capa_id,
        product_id=product_id,
        status="open",
    )
    db.add(alert)
    db.flush()
    return alert


def notify_quality_roles(db: Session, company: Company, settings: QualitySettings, title: str, message: str, link: str) -> None:
    roles = settings.notify_roles_json or DEFAULT_NOTIFY_ROLES
    for role in roles:
        notify_role(
            db,
            company_id=company.id,
            role=role,
            category="system",
            title=title,
            message=message,
            link_path=link,
        )


def on_inspection_failed(db: Session, company: Company, insp: QualityInspection, user: User | None = None) -> None:
    settings = get_quality_settings(db, company)
    product_name = insp.product.name if insp.product else "Item"
    create_quality_alert(
        db,
        company.id,
        alert_type="inspection_failed",
        severity="high",
        title=f"QC failed — {insp.inspection_number}",
        message=f"{product_name} failed inspection.",
        inspection_id=insp.id,
        product_id=insp.product_id,
    )
    notify_quality_roles(
        db,
        company,
        settings,
        f"QC failed: {insp.inspection_number}",
        f"{product_name} failed quality inspection.",
        f"/quality/inspections/{insp.id}",
    )
    if insp.product_id and insp.inspection_point_id:
        check_repeat_failure(db, company, settings, insp)


def check_repeat_failure(db: Session, company: Company, settings: QualitySettings, insp: QualityInspection) -> None:
    threshold = settings.alert_repeat_fail_threshold or DEFAULT_REPEAT_FAIL_THRESHOLD
    since = _utcnow() - timedelta(days=30)
    fail_count = (
        db.query(func.count(QualityInspection.id))
        .filter(
            QualityInspection.company_id == company.id,
            QualityInspection.product_id == insp.product_id,
            QualityInspection.inspection_point_id == insp.inspection_point_id,
            QualityInspection.status == "failed",
            QualityInspection.inspected_at >= since,
        )
        .scalar()
    )
    if int(fail_count or 0) >= threshold:
        product_name = insp.product.name if insp.product else "Product"
        create_quality_alert(
            db,
            company.id,
            alert_type="repeat_failure",
            severity="critical",
            title=f"Repeat QC failures — {product_name}",
            message=f"{product_name} failed {fail_count} times in 30 days at this inspection point.",
            inspection_id=insp.id,
            product_id=insp.product_id,
        )


def sync_overdue_inspection_alerts(db: Session, company: Company) -> None:
    settings = get_quality_settings(db, company)
    if not settings.is_enabled:
        return
    hours = settings.alert_overdue_hours or DEFAULT_OVERDUE_HOURS
    cutoff = _utcnow() - timedelta(hours=hours)
    overdue = (
        db.query(QualityInspection)
        .filter(
            QualityInspection.company_id == company.id,
            QualityInspection.status == "pending",
            QualityInspection.created_at < cutoff,
        )
        .all()
    )
    for insp in overdue:
        exists = (
            db.query(QualityAlert)
            .filter(
                QualityAlert.company_id == company.id,
                QualityAlert.alert_type == "inspection_overdue",
                QualityAlert.inspection_id == insp.id,
                QualityAlert.status == "open",
            )
            .first()
        )
        if not exists:
            create_quality_alert(
                db,
                company.id,
                alert_type="inspection_overdue",
                severity="medium",
                title=f"Overdue inspection — {insp.inspection_number}",
                message="Pending inspection exceeded SLA.",
                inspection_id=insp.id,
                product_id=insp.product_id,
            )


def sync_overdue_capa_alerts(db: Session, company: Company) -> None:
    settings = get_quality_settings(db, company)
    if not settings.is_enabled:
        return
    today = _utcnow().date()
    overdue_capas = (
        db.query(CorrectiveAction)
        .filter(
            CorrectiveAction.company_id == company.id,
            CorrectiveAction.status.in_(["open", "in_progress"]),
            CorrectiveAction.due_date.isnot(None),
            CorrectiveAction.due_date < today,
        )
        .all()
    )
    for capa in overdue_capas:
        exists = (
            db.query(QualityAlert)
            .filter(
                QualityAlert.company_id == company.id,
                QualityAlert.alert_type == "capa_overdue",
                QualityAlert.capa_id == capa.id,
                QualityAlert.status == "open",
            )
            .first()
        )
        if not exists:
            create_quality_alert(
                db,
                company.id,
                alert_type="capa_overdue",
                severity="medium",
                title=f"Overdue CAPA — {capa.capa_number}",
                message=capa.title,
                capa_id=capa.id,
            )
