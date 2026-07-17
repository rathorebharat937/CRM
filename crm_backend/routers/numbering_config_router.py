from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from activity import log_activity
from auth_utils import get_client_ip, get_db, require_permission
from models import NumberingConfiguration, User
from schemas import (
    NumberingConfigCreateRequest,
    NumberingConfigResponse,
    NumberingConfigUpdateRequest,
)
from services.number_generator_service import NumberGeneratorService
from tenant_utils import get_current_company, require_company_record

router = APIRouter(prefix="/admin/numbering-config", tags=["numbering-config"])


def _get_config(db: Session, config_id: int, company_id: int) -> NumberingConfiguration:
    config = (
        db.query(NumberingConfiguration)
        .filter(NumberingConfiguration.id == config_id)
        .first()
    )
    require_company_record(config, company_id, detail="Numbering configuration not found")
    return config


@router.get("", response_model=list[NumberingConfigResponse])
def list_configurations(
    user: User = Depends(require_permission("numbering_config.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    return (
        db.query(NumberingConfiguration)
        .filter(NumberingConfiguration.company_id == company.id)
        .order_by(NumberingConfiguration.entity_name)
        .all()
    )


@router.post("", response_model=NumberingConfigResponse)
def create_configuration(
    data: NumberingConfigCreateRequest,
    request: Request,
    admin: User = Depends(require_permission("numbering_config.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, admin)
    existing = (
        db.query(NumberingConfiguration)
        .filter(
            NumberingConfiguration.company_id == company.id,
            NumberingConfiguration.entity_name == data.entity_name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Configuration for entity '{data.entity_name}' already exists",
        )

    config = NumberingConfiguration(
        company_id=company.id,
        entity_name=data.entity_name.upper(),
        prefix=data.prefix.upper(),
        starting_number=data.starting_number,
        current_number=data.current_number,
        suffix=data.suffix.upper() if data.suffix else None,
        is_active=data.is_active,
    )
    db.add(config)
    db.commit()
    db.refresh(config)

    log_activity(
        db,
        "numbering_config_created",
        user_id=admin.id,
        email=admin.email,
        details=f"Created numbering configuration for {config.entity_name}",
        ip_address=get_client_ip(request),
    )

    return config


@router.put("/{config_id}", response_model=NumberingConfigResponse)
def update_configuration(
    config_id: int,
    data: NumberingConfigUpdateRequest,
    request: Request,
    admin: User = Depends(require_permission("numbering_config.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, admin)
    config = _get_config(db, config_id, company.id)

    if data.prefix is not None:
        config.prefix = data.prefix.upper()
    if data.starting_number is not None:
        config.starting_number = data.starting_number
    if data.current_number is not None:
        config.current_number = data.current_number
    if data.suffix is not None:
        config.suffix = data.suffix.upper() if data.suffix else None
    if data.is_active is not None:
        config.is_active = data.is_active

    db.commit()
    db.refresh(config)

    log_activity(
        db,
        "numbering_config_updated",
        user_id=admin.id,
        email=admin.email,
        details=f"Updated numbering configuration for {config.entity_name}",
        ip_address=get_client_ip(request),
    )

    return config


@router.delete("/{config_id}")
def delete_configuration(
    config_id: int,
    request: Request,
    admin: User = Depends(require_permission("numbering_config.delete")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, admin)
    config = _get_config(db, config_id, company.id)
    entity_name = config.entity_name

    db.delete(config)
    db.commit()

    log_activity(
        db,
        "numbering_config_deleted",
        user_id=admin.id,
        email=admin.email,
        details=f"Deleted numbering configuration for {entity_name}",
        ip_address=get_client_ip(request),
    )

    return {"message": f"Configuration for {entity_name} deleted successfully"}


@router.post("/{config_id}/activate")
def activate_configuration(
    config_id: int,
    request: Request,
    admin: User = Depends(require_permission("numbering_config.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, admin)
    config = _get_config(db, config_id, company.id)
    config.is_active = True
    db.commit()

    log_activity(
        db,
        "numbering_config_activated",
        user_id=admin.id,
        email=admin.email,
        details=f"Activated numbering configuration for {config.entity_name}",
        ip_address=get_client_ip(request),
    )

    return {"message": f"Configuration for {config.entity_name} activated"}


@router.post("/{config_id}/deactivate")
def deactivate_configuration(
    config_id: int,
    request: Request,
    admin: User = Depends(require_permission("numbering_config.edit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, admin)
    config = _get_config(db, config_id, company.id)
    config.is_active = False
    db.commit()

    log_activity(
        db,
        "numbering_config_deactivated",
        user_id=admin.id,
        email=admin.email,
        details=f"Deactivated numbering configuration for {config.entity_name}",
        ip_address=get_client_ip(request),
    )

    return {"message": f"Configuration for {config.entity_name} deactivated"}


@router.post("/generate/{entity_name}")
def generate_number(
    entity_name: str,
    user: User = Depends(require_permission("numbering_config.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    try:
        number = NumberGeneratorService.generate(db, entity_name.upper(), company.id)
        return {"number": number, "entity_name": entity_name.upper()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/preview/{entity_name}")
def preview_next_number(
    entity_name: str,
    user: User = Depends(require_permission("numbering_config.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    try:
        number = NumberGeneratorService.get_next_number(db, entity_name.upper(), company.id)
        return {"next_number": number, "entity_name": entity_name.upper()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
