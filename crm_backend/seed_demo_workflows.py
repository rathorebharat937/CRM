"""Seed demo Workflow Builder (Phase 1 MVP)."""

from __future__ import annotations

import argparse

from database import SessionLocal
from models import Company, User, Workflow
from routers.workflow_router import _get_settings
from services.workflow_engine import generate_workflow_code
from workflow_config import WORKFLOW_TEMPLATES


def seed_demo_workflows(activate: bool = True) -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("No company found. Run seed_company.py first.")
            return

        settings = _get_settings(db, company)
        settings.is_enabled = True
        db.commit()

        admin = db.query(User).filter(User.role == "Admin").first()
        created = 0
        for tpl in WORKFLOW_TEMPLATES:
            exists = (
                db.query(Workflow.id)
                .filter(Workflow.company_id == company.id, Workflow.name == tpl["name"])
                .first()
            )
            if exists:
                continue
            wf = Workflow(
                company_id=company.id,
                workflow_code=generate_workflow_code(db, company.id),
                name=tpl["name"],
                description=tpl.get("description"),
                module=tpl["module"],
                trigger_type=tpl["trigger_type"],
                trigger_config_json=tpl.get("trigger_config_json", {}),
                conditions_json=tpl.get("conditions_json", []),
                actions_json=tpl.get("actions_json", []),
                priority=int(tpl.get("priority", 100)),
                stop_on_match=bool(tpl.get("stop_on_match", False)),
                is_active=activate,
                created_by_id=admin.id if admin else None,
            )
            db.add(wf)
            db.flush()
            created += 1
        db.commit()
        print(f"Workflow Builder enabled. Created {created} template workflow(s).")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Workflow Builder demo data")
    parser.add_argument("--no-activate", action="store_true", help="Create workflows as inactive")
    args = parser.parse_args()
    seed_demo_workflows(activate=not args.no_activate)
