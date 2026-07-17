from __future__ import annotations

from sqlalchemy.orm import Session

from models import NumberingConfiguration


class NumberGeneratorService:
    """Service for generating and managing sequential numbers for CRM entities."""

    @staticmethod
    def generate(db: Session, entity_name: str, company_id: int) -> str:
        config = (
            db.query(NumberingConfiguration)
            .filter(
                NumberingConfiguration.company_id == company_id,
                NumberingConfiguration.entity_name == entity_name,
                NumberingConfiguration.is_active == True,
            )
            .with_for_update()
            .first()
        )

        if not config:
            raise ValueError(
                f"No active numbering configuration found for entity: {entity_name}"
            )

        config.current_number += 1
        db.commit()

        number_str = str(config.current_number).zfill(4)
        parts = [config.prefix, number_str]
        if config.suffix:
            parts.append(config.suffix)

        return "-".join(parts)

    @staticmethod
    def get_next_number(db: Session, entity_name: str, company_id: int) -> str:
        config = (
            db.query(NumberingConfiguration)
            .filter(
                NumberingConfiguration.company_id == company_id,
                NumberingConfiguration.entity_name == entity_name,
                NumberingConfiguration.is_active == True,
            )
            .first()
        )

        if not config:
            raise ValueError(
                f"No active numbering configuration found for entity: {entity_name}"
            )

        next_number = config.current_number + 1
        number_str = str(next_number).zfill(4)

        parts = [config.prefix, number_str]
        if config.suffix:
            parts.append(config.suffix)

        return "-".join(parts)

    @staticmethod
    def reset_counter(db: Session, entity_name: str, company_id: int, new_value: int) -> None:
        config = (
            db.query(NumberingConfiguration)
            .filter(
                NumberingConfiguration.company_id == company_id,
                NumberingConfiguration.entity_name == entity_name,
            )
            .first()
        )

        if not config:
            raise ValueError(f"No numbering configuration found for entity: {entity_name}")

        config.current_number = new_value
        db.commit()
