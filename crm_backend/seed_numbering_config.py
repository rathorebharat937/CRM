from __future__ import annotations

"""Seed default numbering configurations."""

import argparse

from database import SessionLocal
from models import Company, NumberingConfiguration
from services.tenant_bootstrap_service import DEFAULT_NUMBERING


def seed(company_id: int | None = None) -> None:
    db = SessionLocal()
    try:
        if company_id is not None:
            companies = db.query(Company).filter(Company.id == company_id).all()
        else:
            companies = db.query(Company).order_by(Company.id).all()

        if not companies:
            print("SKIP: no companies found — run seed_company.py or register-company first")
            return

        for company in companies:
            for config_data in DEFAULT_NUMBERING:
                entity_name = config_data["entity_name"]
                existing = (
                    db.query(NumberingConfiguration)
                    .filter(
                        NumberingConfiguration.company_id == company.id,
                        NumberingConfiguration.entity_name == entity_name,
                    )
                    .first()
                )
                if not existing:
                    config = NumberingConfiguration(company_id=company.id, **config_data)
                    db.add(config)
                    print(f"CREATE numbering for {entity_name} (company {company.id})")
                else:
                    print(f"SKIP numbering for {entity_name} (company {company.id})")

        db.commit()
        print("Numbering configurations seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-id", type=int, default=None)
    args = parser.parse_args()
    seed(args.company_id)
