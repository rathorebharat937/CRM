from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import Company, EmployeeProfile, Payslip, User
from payroll_config import (
    DEFAULT_HRA_RATE,
    DEFAULT_PF_RATE,
    DEFAULT_TDS_RATE,
    PAYSLIP_STATUS_LABELS,
    PAYSLIP_STATUSES,
)
from permissions import role_has_permission
from schemas import (
    EmployeeOption,
    PayrollMetaResponse,
    PayrollStatsResponse,
    PayslipGenerateRequest,
    PayslipListResponse,
    PayslipResponse,
)

router = APIRouter(prefix="/payroll", tags=["payroll"])

MONTH_LABELS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)




def _float(v) -> float:
    return 0.0 if v is None else float(v)


def _period_label(month: int, year: int) -> str:
    return f"{MONTH_LABELS.get(month, str(month))} {year}"


def _payslip_number(db: Session, company_id: int, year: int) -> str:
    prefix = f"PAY-{year}-"
    last = (
        db.query(Payslip)
        .filter(Payslip.company_id == company_id, Payslip.payslip_number.like(f"{prefix}%"))
        .order_by(Payslip.id.desc())
        .first()
    )
    seq = 1
    if last and last.payslip_number:
        try:
            seq = int(last.payslip_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _payslip_resp(p: Payslip) -> PayslipResponse:
    return PayslipResponse(
        id=p.id,
        payslip_number=p.payslip_number,
        employee_id=p.employee_id,
        employee_name=p.employee.name if p.employee else None,
        period_month=p.period_month,
        period_year=p.period_year,
        period_label=_period_label(p.period_month, p.period_year),
        basic_salary=_float(p.basic_salary),
        hra=_float(p.hra),
        allowances=_float(p.allowances),
        gross_salary=_float(p.gross_salary),
        pf_deduction=_float(p.pf_deduction),
        tds_deduction=_float(p.tds_deduction),
        other_deductions=_float(p.other_deductions),
        reimbursements=_float(p.reimbursements),
        net_salary=_float(p.net_salary),
        status=p.status,
        status_label=PAYSLIP_STATUS_LABELS.get(p.status, p.status),
        payment_date=p.payment_date,
        notes=p.notes,
    )


@router.get("/meta", response_model=PayrollMetaResponse)
def payroll_meta(_: User = Depends(require_permission("payroll.view"))):
    return PayrollMetaResponse(
        statuses=[EmployeeOption(value=k, label=v) for k, v in PAYSLIP_STATUS_LABELS.items()],
    )


@router.get("/stats/summary", response_model=PayrollStatsResponse)
def payroll_stats(
    current_user: User = Depends(require_permission("payroll.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    now = _utcnow()
    month, year = now.month, now.year
    base = db.query(Payslip).filter(
        Payslip.company_id == company.id,
        Payslip.period_month == month,
        Payslip.period_year == year,
    )
    if role_has_permission(db, current_user.role, "payroll.view_all"):
        from sqlalchemy import func
        paid = base.filter(Payslip.status == "paid")
        total_net = paid.with_entities(func.coalesce(func.sum(Payslip.net_salary), 0)).scalar() or 0
        return PayrollStatsResponse(
            generated_this_month=base.count(),
            paid_this_month=paid.count(),
            total_net_this_month=_float(total_net),
        )

    latest = (
        base.filter(Payslip.employee_id == current_user.id)
        .order_by(Payslip.id.desc())
        .first()
    )
    return PayrollStatsResponse(my_latest_net=_float(latest.net_salary) if latest else None)


@router.get("", response_model=PayslipListResponse)
def list_payslips(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    employee_id: int | None = None,
    current_user: User = Depends(require_permission("payroll.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    query = (
        db.query(Payslip)
        .options(joinedload(Payslip.employee))
        .filter(Payslip.company_id == company.id)
        .order_by(Payslip.period_year.desc(), Payslip.period_month.desc(), Payslip.id.desc())
    )
    if employee_id is not None:
        query = query.filter(Payslip.employee_id == employee_id)
    elif not role_has_permission(db, current_user.role, "payroll.view_all"):
        query = query.filter(Payslip.employee_id == current_user.id)

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return PayslipListResponse(items=[_payslip_resp(p) for p in items], total=total, page=page, limit=limit)


@router.get("/{payslip_id}", response_model=PayslipResponse)
def get_payslip(
    payslip_id: int,
    current_user: User = Depends(require_permission("payroll.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    payslip = (
        db.query(Payslip)
        .options(joinedload(Payslip.employee))
        .filter(Payslip.id == payslip_id, Payslip.company_id == company.id)
        .first()
    )
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if payslip.employee_id != current_user.id and not role_has_permission(db, current_user.role, "payroll.view_all"):
        raise HTTPException(status_code=403, detail="Permission denied")
    return _payslip_resp(payslip)


@router.post("/generate", response_model=PayslipResponse)
def generate_payslip(
    payload: PayslipGenerateRequest,
    request: Request,
    current_user: User = Depends(require_permission("payroll.generate")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    if payload.period_month < 1 or payload.period_month > 12:
        raise HTTPException(status_code=400, detail="Invalid month")

    existing = (
        db.query(Payslip)
        .filter(
            Payslip.company_id == company.id,
            Payslip.employee_id == payload.employee_id,
            Payslip.period_month == payload.period_month,
            Payslip.period_year == payload.period_year,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Payslip already exists for this period")

    profile = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.company_id == company.id, EmployeeProfile.user_id == payload.employee_id)
        .first()
    )
    basic = Decimal(str(_float(profile.salary_monthly) if profile and profile.salary_monthly else 25000))
    hra = basic * Decimal(str(DEFAULT_HRA_RATE))
    allowances = basic * Decimal("0.10")
    gross = basic + hra + allowances
    pf = basic * Decimal(str(DEFAULT_PF_RATE))
    tds = gross * Decimal(str(DEFAULT_TDS_RATE))
    other = Decimal(str(payload.other_deductions))
    reimburse = Decimal(str(payload.reimbursements))
    net = gross - pf - tds - other + reimburse

    payslip = Payslip(
        company_id=company.id,
        employee_id=payload.employee_id,
        payslip_number=_payslip_number(db, company.id, payload.period_year),
        period_month=payload.period_month,
        period_year=payload.period_year,
        basic_salary=basic,
        hra=hra,
        allowances=allowances,
        gross_salary=gross,
        pf_deduction=pf,
        tds_deduction=tds,
        other_deductions=other,
        reimbursements=reimburse,
        net_salary=net,
        status="generated",
        notes=payload.notes,
        generated_by_id=current_user.id,
    )
    db.add(payslip)
    db.commit()
    payslip = db.query(Payslip).options(joinedload(Payslip.employee)).filter(Payslip.id == payslip.id).first()
    log_activity(db, action="payslip_generated", user_id=current_user.id, email=current_user.email,
                 details=f"Generated payslip {payslip.payslip_number}", ip_address=get_client_ip(request))
    return _payslip_resp(payslip)


@router.post("/{payslip_id}/mark-paid", response_model=PayslipResponse)
def mark_paid(
    payslip_id: int,
    request: Request,
    current_user: User = Depends(require_permission("payroll.mark_paid")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    payslip = db.query(Payslip).filter(Payslip.id == payslip_id, Payslip.company_id == company.id).first()
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    payslip.status = "paid"
    payslip.payment_date = _utcnow()
    db.commit()
    payslip = db.query(Payslip).options(joinedload(Payslip.employee)).filter(Payslip.id == payslip.id).first()
    log_activity(db, action="payslip_paid", user_id=current_user.id, email=current_user.email,
                 details=f"Marked paid {payslip.payslip_number}", ip_address=get_client_ip(request))
    return _payslip_resp(payslip)
