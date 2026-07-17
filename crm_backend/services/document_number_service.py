from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Company, Invoice, Quotation, SystemSetting
from services.number_generator_service import NumberGeneratorService


def _legacy_quote_number(db: Session, company: Company) -> str:
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == company.id).first()
    prefix = settings.quote_prefix if settings else "Quote-"
    count = db.query(func.count(Quotation.id)).filter(Quotation.company_id == company.id).scalar()
    return f"{prefix}{count + 1:05d}"


def _legacy_invoice_number(db: Session, company: Company) -> str:
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == company.id).first()
    prefix = settings.invoice_prefix if settings else "Inv-"
    count = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.company_id == company.id, Invoice.invoice_number.isnot(None))
        .scalar()
    )
    return f"{prefix}{count + 1:05d}"


def generate_quote_number(db: Session, company: Company) -> str:
    try:
        return NumberGeneratorService.generate(db, "QUOTATION", company.id)
    except ValueError:
        return _legacy_quote_number(db, company)


def generate_invoice_number(db: Session, company: Company) -> str:
    try:
        return NumberGeneratorService.generate(db, "INVOICE", company.id)
    except ValueError:
        return _legacy_invoice_number(db, company)
