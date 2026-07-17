from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from models import Company, JobApplicant, JobOpening, User
from recruitment_config import APPLICANT_STATUS_LABELS, APPLICANT_STATUSES, JOB_STATUS_LABELS, JOB_STATUSES
from schemas import (
    EmployeeOption,
    JobApplicantCreateRequest,
    JobApplicantResponse,
    JobApplicantUpdateRequest,
    JobOpeningCreateRequest,
    JobOpeningDetailResponse,
    JobOpeningListResponse,
    JobOpeningResponse,
    JobOpeningUpdateRequest,
    RecruitmentMetaResponse,
)

router = APIRouter(prefix="/recruitment", tags=["recruitment"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)




def _float(v) -> float | None:
    return None if v is None else float(v)


def _job_code(db: Session, company_id: int) -> str:
    year = _utcnow().year
    prefix = f"JOB-{year}-"
    last = (
        db.query(JobOpening)
        .filter(JobOpening.company_id == company_id, JobOpening.job_code.like(f"{prefix}%"))
        .order_by(JobOpening.id.desc())
        .first()
    )
    seq = 1
    if last and last.job_code:
        try:
            seq = int(last.job_code.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:03d}"


def _job_resp(job: JobOpening, applicant_count: int | None = None) -> JobOpeningResponse:
    count = applicant_count
    if count is None:
        count = len(job.applicants) if job.applicants is not None else 0
    return JobOpeningResponse(
        id=job.id,
        job_code=job.job_code,
        title=job.title,
        department=job.department,
        description=job.description,
        status=job.status,
        status_label=JOB_STATUS_LABELS.get(job.status, job.status),
        openings_count=job.openings_count,
        salary_min=_float(job.salary_min),
        salary_max=_float(job.salary_max),
        posted_at=job.posted_at,
        applicant_count=count,
        notes=job.notes,
    )


def _applicant_resp(a: JobApplicant) -> JobApplicantResponse:
    return JobApplicantResponse(
        id=a.id,
        job_opening_id=a.job_opening_id,
        name=a.name,
        email=a.email,
        phone=a.phone,
        status=a.status,
        status_label=APPLICANT_STATUS_LABELS.get(a.status, a.status),
        interview_round=a.interview_round,
        experience_years=_float(a.experience_years),
        current_company=a.current_company,
        resume_summary=a.resume_summary,
        interviewer_note=a.interviewer_note,
        applied_at=a.applied_at,
    )


@router.get("/meta", response_model=RecruitmentMetaResponse)
def recruitment_meta(_: User = Depends(require_permission("recruitment.view"))):
    return RecruitmentMetaResponse(
        job_statuses=[EmployeeOption(value=k, label=v) for k, v in JOB_STATUS_LABELS.items()],
        applicant_statuses=[EmployeeOption(value=k, label=v) for k, v in APPLICANT_STATUS_LABELS.items()],
    )


@router.get("/jobs", response_model=JobOpeningListResponse)
def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    user: User = Depends(require_permission("recruitment.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = db.query(JobOpening).filter(JobOpening.company_id == company.id)
    if status:
        query = query.filter(JobOpening.status == status)
    query = query.order_by(JobOpening.posted_at.desc().nullslast(), JobOpening.id.desc())
    total = query.count()
    jobs = query.offset((page - 1) * limit).limit(limit).all()
    counts = dict(
        db.query(JobApplicant.job_opening_id, func.count(JobApplicant.id))
        .filter(JobApplicant.job_opening_id.in_([j.id for j in jobs]))
        .group_by(JobApplicant.job_opening_id)
        .all()
    ) if jobs else {}
    return JobOpeningListResponse(
        items=[_job_resp(j, counts.get(j.id, 0)) for j in jobs],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/jobs", response_model=JobOpeningResponse)
def create_job(
    payload: JobOpeningCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("recruitment.manage")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    if payload.status not in JOB_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    job = JobOpening(
        company_id=company.id,
        job_code=_job_code(db, company.id),
        title=payload.title.strip(),
        department=payload.department,
        description=payload.description,
        status=payload.status,
        openings_count=payload.openings_count,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        posted_at=_utcnow() if payload.status == "open" else None,
        created_by_id=current_user.id,
        notes=payload.notes,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    log_activity(db, action="job_opening_created", user_id=current_user.id, email=current_user.email,
                 details=f"Created job {job.job_code}", ip_address=get_client_ip(request))
    return _job_resp(job, 0)


@router.get("/jobs/{job_id}", response_model=JobOpeningDetailResponse)
def get_job(
    job_id: int,
    user: User = Depends(require_permission("recruitment.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    job = (
        db.query(JobOpening)
        .options(joinedload(JobOpening.applicants))
        .filter(JobOpening.id == job_id, JobOpening.company_id == company.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found")
    base = _job_resp(job)
    return JobOpeningDetailResponse(
        **base.model_dump(),
        applicants=[_applicant_resp(a) for a in sorted(job.applicants, key=lambda x: x.id, reverse=True)],
    )


@router.put("/jobs/{job_id}", response_model=JobOpeningResponse)
def update_job(
    job_id: int,
    payload: JobOpeningUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("recruitment.manage")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    job = db.query(JobOpening).filter(JobOpening.id == job_id, JobOpening.company_id == company.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found")
    if payload.status and payload.status not in JOB_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    for field in ("title", "department", "description", "status", "openings_count", "salary_min", "salary_max", "notes"):
        val = getattr(payload, field)
        if val is not None:
            setattr(job, field, val.strip() if isinstance(val, str) else val)
    if payload.status == "closed" and not job.closed_at:
        job.closed_at = _utcnow()
    db.commit()
    log_activity(db, action="job_opening_updated", user_id=current_user.id, email=current_user.email,
                 details=f"Updated job {job.job_code}", ip_address=get_client_ip(request))
    return _job_resp(job)


@router.post("/jobs/{job_id}/applicants", response_model=JobApplicantResponse)
def add_applicant(
    job_id: int,
    payload: JobApplicantCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("recruitment.manage")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, current_user)
    job = db.query(JobOpening).filter(JobOpening.id == job_id, JobOpening.company_id == company.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found")
    applicant = JobApplicant(
        job_opening_id=job.id,
        name=payload.name.strip(),
        email=payload.email.strip().lower(),
        phone=payload.phone,
        experience_years=payload.experience_years,
        current_company=payload.current_company,
        resume_summary=payload.resume_summary,
    )
    db.add(applicant)
    db.commit()
    db.refresh(applicant)
    log_activity(db, action="applicant_added", user_id=current_user.id, email=current_user.email,
                 details=f"Applicant {applicant.name} for {job.job_code}", ip_address=get_client_ip(request))
    return _applicant_resp(applicant)


@router.put("/applicants/{applicant_id}", response_model=JobApplicantResponse)
def update_applicant(
    applicant_id: int,
    payload: JobApplicantUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("recruitment.manage")),
    db: Session = Depends(get_db),
):
    applicant = db.query(JobApplicant).filter(JobApplicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    if payload.status and payload.status not in APPLICANT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    for field in ("status", "interview_round", "interviewer_note", "resume_summary"):
        val = getattr(payload, field)
        if val is not None:
            setattr(applicant, field, val)
    db.commit()
    db.refresh(applicant)
    log_activity(db, action="applicant_updated", user_id=current_user.id, email=current_user.email,
                 details=f"Updated applicant {applicant.name}", ip_address=get_client_ip(request))
    return _applicant_resp(applicant)
