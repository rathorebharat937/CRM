from __future__ import annotations

from sqlalchemy.orm import Session

from level2_defaults import SYSTEM_SETTING_DEFAULTS
from models import Company, NumberingConfiguration, SystemSetting, User, WebsiteSettings
from website_config import normalize_slug

DEFAULT_NUMBERING = [
    {"entity_name": "CONTACT", "prefix": "CNT", "starting_number": 1, "current_number": 0},
    {"entity_name": "LEAD", "prefix": "LEAD", "starting_number": 1, "current_number": 0},
    {"entity_name": "QUOTATION", "prefix": "QUO", "starting_number": 1, "current_number": 0},
    {"entity_name": "INVOICE", "prefix": "INV", "starting_number": 1000, "current_number": 1000},
    {"entity_name": "PAYMENT", "prefix": "PAY", "starting_number": 1, "current_number": 0},
    {"entity_name": "TASK", "prefix": "TASK", "starting_number": 1, "current_number": 0},
    {"entity_name": "EMPLOYEE", "prefix": "EMP", "starting_number": 1, "current_number": 0},
]


def _unique_website_slug(db: Session, base_name: str, company_id: int) -> str:
    base_slug = normalize_slug(base_name) or f"company-{company_id}"
    slug = base_slug
    suffix = 0
    while db.query(WebsiteSettings).filter(WebsiteSettings.company_slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    return slug


def bootstrap_tenant_defaults(db: Session, company: Company) -> None:
    """Create per-tenant settings, numbering, and public site slug."""
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == company.id).first()
    if not settings:
        settings = SystemSetting(company_id=company.id)
        db.add(settings)
    for key, value in SYSTEM_SETTING_DEFAULTS.items():
        setattr(settings, key, value)

    for config_data in DEFAULT_NUMBERING:
        existing = (
            db.query(NumberingConfiguration)
            .filter(
                NumberingConfiguration.company_id == company.id,
                NumberingConfiguration.entity_name == config_data["entity_name"],
            )
            .first()
        )
        if not existing:
            db.add(NumberingConfiguration(company_id=company.id, **config_data))

    site = db.query(WebsiteSettings).filter(WebsiteSettings.company_id == company.id).first()
    if not site:
        slug = _unique_website_slug(
            db,
            company.display_name or company.legal_name,
            company.id,
        )
        db.add(WebsiteSettings(company_id=company.id, company_slug=slug))


def create_company_with_admin(
    db: Session,
    *,
    legal_name: str,
    display_name: str,
    owner_name: str,
    owner_email: str,
    password_hash: str,
    phone: str | None = None,
    email: str | None = None,
) -> tuple[Company, User]:
    """Atomically create a company workspace and its first Admin user."""
    company = Company(
        legal_name=legal_name.strip(),
        display_name=display_name.strip(),
        email=(email or owner_email).lower(),
        phone=phone,
    )
    db.add(company)
    db.flush()

    admin = User(
        company_id=company.id,
        name=owner_name.strip(),
        email=owner_email.lower(),
        phone=phone,
        password=password_hash,
        role="Admin",
        status="active",
    )
    db.add(admin)
    db.flush()

    bootstrap_tenant_defaults(db, company)
    return company, admin
