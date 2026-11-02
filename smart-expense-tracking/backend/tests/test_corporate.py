import pytest

from app import create_app
from extensions import db


class TestConfig:
    TESTING = True
    SECRET_KEY = "corporate-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ["http://localhost:5173"]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    ADMIN_EMAILS = set()


@pytest.fixture
def app():
    test_app = create_app(TestConfig)
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_headers(client):
    response = client.get("/api/auth/csrf")
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def register_organization(client, email="owner@example.com"):
    response = client.post(
        "/api/corporate/organizations",
        json={
            "name": "Owner",
            "email": email,
            "password": "secure password 123",
            "organization_name": "Acme Corporate",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    return response.json["data"]["organization"]["joining_code"]


def login(client, email, mode="corporate"):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": "secure password 123", "mode": mode},
        headers=csrf_headers(client),
    )


def test_corporate_registration_join_and_approval_workflow(client):
    joining_code = register_organization(client)
    admin_login = login(client, "owner@example.com")
    assert admin_login.status_code == 200
    assert admin_login.json["data"]["user"]["role"] == "Admin"

    employee = client.application.test_client()
    joined = employee.post(
        "/api/corporate/join",
        json={
            "name": "Employee",
            "email": "employee@example.com",
            "password": "secure password 123",
            "joining_code": joining_code.lower(),
        },
        headers=csrf_headers(employee),
    )
    assert joined.status_code == 201
    assert login(employee, "employee@example.com").status_code == 200
    submitted = employee.post(
        "/api/corporate/expenses",
        json={"amount": "42.50", "date": "2026-04-15", "category": "Travel", "merchant": "Metro"},
        headers=csrf_headers(employee),
    )
    assert submitted.status_code == 201
    expense_id = submitted.json["data"]["expense"]["expense_id"]
    assert submitted.json["data"]["expense"]["status"] == "Pending Manager"
    own_decision = employee.post(
        f"/api/corporate/expenses/{expense_id}/decision",
        json={"approve": True},
        headers=csrf_headers(employee),
    )
    assert own_decision.status_code == 403

    # Managers cannot skip the manager review step and approve directly as finance.
    manager = client.application.test_client()
    manager_join = manager.post(
        "/api/corporate/join",
        json={
            "name": "Manager",
            "email": "manager@example.com",
            "password": "secure password 123",
            "joining_code": joining_code,
        },
        headers=csrf_headers(manager),
    )
    assert manager_join.status_code == 201
    assert login(manager, "manager@example.com").status_code == 200
    members = client.get("/api/corporate/members")
    manager_membership = next(
        item for item in members.json["data"]["members"] if item["email"] == "manager@example.com"
    )
    updated = client.patch(
        f"/api/corporate/members/{manager_membership['membership_id']}",
        json={"role": "Manager"},
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200
    manager.post("/api/auth/logout", headers=csrf_headers(manager))
    assert login(manager, "manager@example.com").status_code == 200

    decision_url = f"/api/corporate/expenses/{expense_id}/decision"
    manager_decision = manager.post(decision_url, json={"approve": True}, headers=csrf_headers(manager))
    assert manager_decision.status_code == 200
    assert manager_decision.json["data"]["expense"]["status"] == "Pending Finance"
    manager_second_decision = manager.post(decision_url, json={"approve": True}, headers=csrf_headers(manager))
    assert manager_second_decision.status_code == 403

    finance = client.application.test_client()
    finance_join = finance.post(
        "/api/corporate/join",
        json={
            "name": "Finance",
            "email": "finance@example.com",
            "password": "secure password 123",
            "joining_code": joining_code,
        },
        headers=csrf_headers(finance),
    )
    assert finance_join.status_code == 201
    members = client.get("/api/corporate/members")
    finance_membership = next(
        item for item in members.json["data"]["members"] if item["email"] == "finance@example.com"
    )
    updated = client.patch(
        f"/api/corporate/members/{finance_membership['membership_id']}",
        json={"role": "Finance Officer"},
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200
    assert login(finance, "finance@example.com").status_code == 200
    finance_decision = finance.post(decision_url, json={"approve": True}, headers=csrf_headers(finance))
    assert finance_decision.status_code == 200
    assert finance_decision.json["data"]["expense"]["status"] == "Approved"

    history = employee.get("/api/corporate/expenses")
    assert history.status_code == 200
    assert len(history.json["data"]["expenses"]) == 1
    assert history.json["data"]["expenses"][0]["status"] == "Approved"


def test_personal_registration_and_login_stay_in_personal_mode(client):
    response = client.post(
        "/api/auth/register",
        json={"name": "Personal User", "email": "personal@example.com", "password": "secure password 123"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    signed_in = login(client, "personal@example.com", mode="personal")
    assert signed_in.status_code == 200
    assert signed_in.json["data"]["user"]["workspace_mode"] == "personal"


def test_corporate_login_requires_a_corporate_membership(client):
    client.post(
        "/api/auth/register",
        json={"name": "Personal User", "email": "personal@example.com", "password": "secure password 123"},
        headers=csrf_headers(client),
    )
    response = login(client, "personal@example.com", mode="corporate")
    assert response.status_code == 403


def test_demo_seed_is_idempotent_and_covers_three_months(app):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["seed-corporate-demo"])
    assert first.exit_code == 0
    assert "Joining code:" in first.output
    second = runner.invoke(args=["seed-corporate-demo"])
    assert second.exit_code == 0
    assert "already exists" in second.output
    with app.app_context():
        from models import CorporateExpense, Organization

        organization = Organization.query.filter_by(name="Northstar Demo Corporation").one()
        expenses = CorporateExpense.query.filter_by(organization_id=organization.organization_id).all()
        assert len(expenses) == 9
        assert len({(expense.expense_date.year, expense.expense_date.month) for expense in expenses}) == 3
