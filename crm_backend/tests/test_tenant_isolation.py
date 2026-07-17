"""Multi-tenant isolation tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from auth_utils import hash_password
from database import SessionLocal
from main import app
from models import Company, Lead, User
from services.tenant_bootstrap_service import create_company_with_admin


@pytest.fixture()
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _register_via_api(client: TestClient, email: str, company_name: str) -> dict:
    response = client.post(
        "/register-company",
        json={
            "owner_name": "Owner",
            "owner_email": email,
            "password": "secret123",
            "company_legal_name": company_name,
            "company_display_name": company_name,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_register_company_creates_admin_workspace(client: TestClient):
    payload = _register_via_api(client, "tenant-a@test.com", "Tenant A Pvt Ltd")
    assert payload["role"] == "Admin"
    assert payload["company_id"] > 0
    assert payload["company_name"] == "Tenant A Pvt Ltd"
    assert payload["access_token"]


def test_tenant_cannot_read_other_tenant_leads(client: TestClient, db: Session):
    a = _register_via_api(client, "tenant-a2@test.com", "Tenant A2")
    b = _register_via_api(client, "tenant-b2@test.com", "Tenant B2")

    lead = Lead(
        company_id=a["company_id"],
        name="Secret Lead",
        phone="9999999999",
        source="Website",
        status="new",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    own = client.get("/leads", headers={"Authorization": f"Bearer {a['access_token']}"})
    assert own.status_code == 200
    own_ids = {item["id"] for item in own.json()["items"]}
    assert lead.id in own_ids

    other = client.get("/leads", headers={"Authorization": f"Bearer {b['access_token']}"})
    assert other.status_code == 200
    other_ids = {item["id"] for item in other.json()["items"]}
    assert lead.id not in other_ids

    blocked = client.get(
        f"/leads/{lead.id}",
        headers={"Authorization": f"Bearer {b['access_token']}"},
    )
    assert blocked.status_code == 404


def test_login_rejects_staff_without_company(client: TestClient, db: Session):
    orphan = User(
        name="Orphan Admin",
        email="orphan@test.com",
        password=hash_password("secret123"),
        role="Admin",
        status="active",
        company_id=None,
    )
    db.add(orphan)
    db.commit()

    response = client.post("/login", json={"email": "orphan@test.com", "password": "secret123"})
    assert response.status_code == 403
