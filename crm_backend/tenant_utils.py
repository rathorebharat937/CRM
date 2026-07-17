from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth_utils import get_current_user, get_db
from models import Company, User


def get_current_company(db: Session, user: User) -> Company:
    """Resolve the authenticated user's company workspace."""
    if user.company_id is None:
        raise HTTPException(
            status_code=403,
            detail="No company workspace assigned. Register your business or ask an admin for access.",
        )

    company = db.query(Company).filter(Company.id == user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company workspace not found")
    return company


def require_company_record(
    record,
    company_id: int,
    *,
    detail: str = "Record not found",
) -> None:
    """Raise 404 when a record is missing or belongs to another tenant."""
    if record is None or getattr(record, "company_id", None) != company_id:
        raise HTTPException(status_code=404, detail=detail)


def tenant_company(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    """FastAPI dependency for tenant-scoped company resolution."""
    return get_current_company(db, user)


def get_company_by_id(db: Session, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
