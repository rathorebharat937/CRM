from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import ALLOWED_EXTENSIONS, UPLOAD_DIR
from models import Company, SystemSetting, User
from schemas import SystemSettingResponse, SystemSettingUpdateRequest

router = APIRouter(prefix="/admin", tags=["settings"])

BRANDING_DIR = os.path.join(UPLOAD_DIR, "branding")




def _get_or_create_settings(db: Session, company: Company) -> SystemSetting:
    settings = db.query(SystemSetting).filter(SystemSetting.company_id == company.id).first()
    if not settings:
        settings = SystemSetting(company_id=company.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/settings", response_model=SystemSettingResponse)
def get_system_settings(
    user: User = Depends(require_permission("settings.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    return _get_or_create_settings(db, company)


@router.put("/settings", response_model=SystemSettingResponse)
def update_system_settings(
    data: SystemSettingUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("settings.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    settings = _get_or_create_settings(db, company)
    settings.quote_prefix = data.quote_prefix.strip()
    settings.invoice_prefix = data.invoice_prefix.strip()
    settings.quote_date_format = data.quote_date_format.strip()
    settings.invoice_date_format = data.invoice_date_format.strip()
    settings.default_lead_source = data.default_lead_source.strip()
    db.commit()
    db.refresh(settings)
    log_activity(
        db,
        "settings_updated",
        user_id=user.id,
        email=user.email,
        details="Updated document branding settings",
        ip_address=get_client_ip(request),
    )
    return settings


@router.post("/settings/logo", response_model=SystemSettingResponse)
async def upload_company_logo(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("settings.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    settings = _get_or_create_settings(db, company)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS or ext not in {"png", "jpg", "jpeg", "gif", "svg"}:
        raise HTTPException(status_code=400, detail="Logo must be PNG, JPG, GIF, or SVG")

    os.makedirs(BRANDING_DIR, exist_ok=True)
    stored = f"company-logo-{company.id}-{uuid.uuid4().hex[:8]}.{ext}"
    dest = os.path.join(BRANDING_DIR, stored)
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo must be under 2 MB")
    with open(dest, "wb") as fh:
        fh.write(content)

    if settings.logo_filename:
        old = os.path.join(BRANDING_DIR, settings.logo_filename)
        if os.path.isfile(old):
            try:
                os.remove(old)
            except OSError:
                pass

    settings.logo_filename = stored
    db.commit()
    db.refresh(settings)
    log_activity(
        db,
        "company_logo_updated",
        user_id=user.id,
        email=user.email,
        details="Uploaded company logo",
        ip_address=get_client_ip(request),
    )
    return settings


@router.get("/settings/logo")
def get_company_logo(
    user: User = Depends(require_permission("settings.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    settings = _get_or_create_settings(db, company)
    if not settings.logo_filename:
        raise HTTPException(status_code=404, detail="No logo uploaded")
    path = os.path.join(BRANDING_DIR, settings.logo_filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Logo file missing")
    return FileResponse(path)
