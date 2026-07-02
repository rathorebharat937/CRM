"""Seed demo AI Assistant."""

from database import SessionLocal
from models import AiAssistantSettings, Company


def seed_demo_ai_assistant() -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).first()
        if not company:
            print("No company found. Run seed_company.py first.")
            return
        settings = db.query(AiAssistantSettings).filter(AiAssistantSettings.company_id == company.id).first()
        if not settings:
            settings = AiAssistantSettings(company_id=company.id, is_enabled=True)
            db.add(settings)
        else:
            settings.is_enabled = True
        db.commit()
        print("AI Assistant enabled.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_ai_assistant()
