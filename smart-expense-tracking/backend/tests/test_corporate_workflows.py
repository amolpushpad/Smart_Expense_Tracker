from io import BytesIO

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from extensions import db


class TestConfig:
    TESTING = True
    SECRET_KEY = "corporate-workflow-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ["http://localhost:5173"]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    ADMIN_EMAILS = set()


@pytest.fixture
def app(tmp_path):
    test_app = create_app(TestConfig)
    test_app.config["CORPORATE_RECEIPT_DIR"] = str(tmp_path / "receipts")
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


def create_organization(client):
    response = client.post(
        "/api/corporate/organizations",
        json={
            "name": "Organization Admin",
            "email": "admin@workflow.example",
            "password": "secure password 123",
            "organization_name": "Workflow Company",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    code = response.json["data"]["organization"]["joining_code"]
    signed_in = client.post(
        "/api/auth/login",
        json={"email": "admin@workflow.example", "password": "secure password 123", "mode": "corporate"},
        headers=csrf_headers(client),
    )
    assert signed_in.status_code == 200
    return code


def join_member(client, code, name, email):
    joined = client.post(
        "/api/corporate/join",
        json={
            "name": name,
            "email": email,
            "password": "secure password 123",
            "joining_code": code,
        },
        headers=csrf_headers(client),
    )
    assert joined.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "secure password 123", "mode": "corporate"},
        headers=csrf_headers(client),
    )
    assert login.status_code == 200


def test_receipt_submission_and_download_are_authenticated_and_scoped(client, tmp_path):
    code = create_organization(client)
    employee = client.application.test_client()
    join_member(employee, code, "Employee", "employee@workflow.example")
    response = employee.post(
        "/api/corporate/expenses/with-receipt",
        data={
            "amount": "18.25",
            "date": "2026-03-10",
            "category": "Travel",
            "merchant": "City Bus",
            "description": "",
            "receipt": (BytesIO(b"\x89PNG\r\n\x1a\nimage-data"), "fare.png"),
        },
        headers=csrf_headers(employee),
    )
    assert response.status_code == 201
    expense = response.json["data"]["expense"]
    assert expense["submitter"] == "Employee"
    assert expense["has_receipt"] is True
    assert expense["status"] == "Pending Manager"
    downloaded = employee.get(f"/api/corporate/expenses/{expense['expense_id']}/receipt")
    assert downloaded.status_code == 200
    assert downloaded.data.startswith(b"\x89PNG")

    anonymous = client.application.test_client()
    unauthorized = anonymous.get(f"/api/corporate/expenses/{expense['expense_id']}/receipt")
    assert unauthorized.status_code == 401
    assert list((tmp_path / "receipts").rglob("*.*"))


def test_receipt_file_and_expense_values_are_validated(client):
    code = create_organization(client)
    employee = client.application.test_client()
    join_member(employee, code, "Employee", "employee2@workflow.example")
    invalid_file = employee.post(
        "/api/corporate/expenses/with-receipt",
        data={
            "amount": "18.25",
            "date": "2026-03-10",
            "category": "Travel",
            "merchant": "City Bus",
            "receipt": (BytesIO(b"not-a-pdf"), "receipt.pdf"),
        },
        headers=csrf_headers(employee),
    )
    assert invalid_file.status_code == 400
    oversized_file = employee.post(
        "/api/corporate/expenses/with-receipt",
        data={
            "amount": "18.25",
            "date": "2026-03-10",
            "category": "Travel",
            "merchant": "City Bus",
            "receipt": (BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)), "large.png"),
        },
        headers=csrf_headers(employee),
    )
    assert oversized_file.status_code == 400
    invalid_amount = employee.post(
        "/api/corporate/expenses/with-receipt",
        data={
            "amount": "-1",
            "date": "2026-03-10",
            "category": "Travel",
            "merchant": "City Bus",
        },
        headers=csrf_headers(employee),
    )
    assert invalid_amount.status_code == 400
    assert "amount" in invalid_amount.json["errors"]


def test_database_failure_rolls_back_expense_and_removes_uploaded_receipt(client, app, monkeypatch, tmp_path):
    code = create_organization(client)
    employee = client.application.test_client()
    join_member(employee, code, "Employee", "employee4@workflow.example")

    def fail_commit():
        raise SQLAlchemyError("simulated database failure")

    monkeypatch.setattr(db.session, "commit", fail_commit)
    response = employee.post(
        "/api/corporate/expenses/with-receipt",
        data={
            "amount": "18.25",
            "date": "2026-03-10",
            "category": "Travel",
            "merchant": "City Bus",
            "receipt": (BytesIO(b"\x89PNG\r\n\x1a\nimage-data"), "fare.png"),
        },
        headers=csrf_headers(employee),
    )
    assert response.status_code == 500
    with app.app_context():
        from models import CorporateExpense

        assert CorporateExpense.query.count() == 0
    assert not list((tmp_path / "receipts").rglob("*.*"))


def test_approval_and_reimbursement_totals_include_paid_expenses(client):
    code = create_organization(client)
    employee = client.application.test_client()
    join_member(employee, code, "Employee", "employee3@workflow.example")
    submitted = employee.post(
        "/api/corporate/expenses",
        json={"amount": "125.50", "date": "2026-03-12", "category": "Travel", "merchant": "Taxi"},
        headers=csrf_headers(employee),
    )
    expense_id = submitted.json["data"]["expense"]["expense_id"]

    manager = client.application.test_client()
    join_member(manager, code, "Manager", "manager@workflow.example")
    members = client.get("/api/corporate/members").json["data"]["members"]
    manager_member = next(item for item in members if item["email"] == "manager@workflow.example")
    department = manager_member["department_id"]
    updated = client.patch(
        f"/api/corporate/members/{manager_member['membership_id']}",
        json={"role": "Manager", "department_id": department},
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200
    manager.post("/api/auth/logout", headers=csrf_headers(manager))
    manager.post(
        "/api/auth/login",
        json={"email": "manager@workflow.example", "password": "secure password 123", "mode": "corporate"},
        headers=csrf_headers(manager),
    )

    queue = manager.get("/api/corporate/approvals?queue=manager")
    assert queue.status_code == 200
    assert [row["expense_id"] for row in queue.json["data"]["expenses"]] == [expense_id]
    decision = manager.post(
        f"/api/corporate/approvals/{expense_id}/approve",
        json={"comments": "Reviewed"},
        headers=csrf_headers(manager),
    )
    assert decision.status_code == 200
    assert decision.json["data"]["expense"]["status"] == "Pending Finance"

    finance_decision = client.post(
        f"/api/corporate/approvals/{expense_id}/approve",
        json={"comments": "Finance approved"},
        headers=csrf_headers(client),
    )
    assert finance_decision.status_code == 200
    paid = client.post(
        f"/api/corporate/approvals/{expense_id}/pay",
        json={},
        headers=csrf_headers(client),
    )
    assert paid.status_code == 200
    assert paid.json["data"]["expense"]["paid_at"]

    report = client.get("/api/corporate/reports/summary")
    summary = report.json["data"]["summary"]
    assert summary["submitted_count"] == 1
    assert summary["submitted_amount"] == "125.50"
    assert summary["approved_count"] == 0
    assert summary["paid_count"] == 1
    assert summary["paid_amount"] == "125.50"


def test_role_dashboards_and_expense_search_enforce_role_access(client):
    code = create_organization(client)
    employee = client.application.test_client()
    join_member(employee, code, "Employee", "employee5@workflow.example")
    employee.post(
        "/api/corporate/expenses",
        json={"amount": "40.00", "date": "2026-03-15", "category": "Meals", "merchant": "Lunch Cafe"},
        headers=csrf_headers(employee),
    )

    admin_dashboard = client.get("/api/corporate/dashboard/admin")
    assert admin_dashboard.status_code == 200
    assert admin_dashboard.json["data"]["summary"]["expense_count"] == 1
    denied_dashboard = client.get("/api/corporate/dashboard/executive")
    assert denied_dashboard.status_code == 403

    employee_dashboard = employee.get("/api/corporate/dashboard/employee")
    assert employee_dashboard.status_code == 200
    search = employee.get("/api/corporate/expenses/search?page=1&per_page=10")
    assert search.status_code == 200
    assert search.json["data"]["pagination"]["total"] == 1
    assert search.json["data"]["expenses"][0]["merchant"] == "Lunch Cafe"


def test_joining_can_be_disabled_and_inactive_members_cannot_log_in(client):
    code = create_organization(client)
    employee = client.application.test_client()
    join_member(employee, code, "Existing Employee", "existing@workflow.example")
    employee_membership = next(
        item for item in client.get("/api/corporate/members").json["data"]["members"]
        if item["email"] == "existing@workflow.example"
    )
    deactivated = client.put(
        f"/api/corporate/members/{employee_membership['membership_id']}",
        json={"membership_status": "inactive"},
        headers=csrf_headers(client),
    )
    assert deactivated.status_code == 200
    employee.post("/api/auth/logout", headers=csrf_headers(employee))
    denied_login = employee.post(
        "/api/auth/login",
        json={"email": "existing@workflow.example", "password": "secure password 123", "mode": "corporate"},
        headers=csrf_headers(employee),
    )
    assert denied_login.status_code == 403

    disabled = client.put(
        "/api/corporate/organization",
        json={"joining_enabled": False, "name": "Workflow Company"},
        headers=csrf_headers(client),
    )
    assert disabled.status_code == 200
    joining_client = client.application.test_client()
    blocked_join = joining_client.post(
        "/api/corporate/join",
        json={
            "name": "New Employee",
            "email": "new@workflow.example",
            "password": "secure password 123",
            "joining_code": code,
        },
        headers=csrf_headers(joining_client),
    )
    assert blocked_join.status_code == 403


def test_corporate_workflow_migration_is_additive_and_idempotent(app):
    with app.app_context():
        from datetime import date
        from decimal import Decimal

        from models import Category, Expense, User

        user = User(name="Personal User", email="preserved@workflow.example")
        user.set_password("secure password 123")
        category = Category(category_name="Groceries")
        db.session.add(user)
        db.session.add(category)
        db.session.flush()
        personal_expense = Expense(
            user_id=user.user_id,
            category_id=category.category_id,
            amount=Decimal("23.50"),
            date=date(2026, 3, 5),
            vendor="Local Store",
        )
        db.session.add(personal_expense)
        db.session.commit()
        user_id = user.user_id
        expense_id = personal_expense.expense_id

        legacy_schema = (
            "CREATE TABLE corporate_organizations (organization_id INTEGER PRIMARY KEY, name VARCHAR(160) NOT NULL UNIQUE, joining_code VARCHAR(24) NOT NULL UNIQUE, created_at DATETIME NOT NULL)",
            "CREATE TABLE corporate_departments (department_id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, name VARCHAR(100) NOT NULL, created_at DATETIME NOT NULL, CONSTRAINT uq_corporate_department_name UNIQUE (organization_id, name))",
            "CREATE TABLE corporate_memberships (membership_id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, user_id INTEGER NOT NULL, department_id INTEGER, role VARCHAR(30) NOT NULL DEFAULT 'Employee', CONSTRAINT uq_corporate_membership_user UNIQUE (organization_id, user_id), CONSTRAINT ck_corporate_membership_role CHECK (role IN ('Admin', 'Employee', 'Manager', 'Finance Officer', 'Executive')))",
            "CREATE TABLE corporate_expenses (expense_id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, submitter_id INTEGER NOT NULL, department_id INTEGER, amount NUMERIC(12, 2) NOT NULL, expense_date DATE NOT NULL, category VARCHAR(80) NOT NULL, merchant VARCHAR(160) NOT NULL, description VARCHAR(500), status VARCHAR(24) NOT NULL DEFAULT 'Pending Manager', manager_id INTEGER, manager_note VARCHAR(500), finance_id INTEGER, finance_note VARCHAR(500), created_at DATETIME NOT NULL, CONSTRAINT ck_corporate_expense_positive_amount CHECK (amount > 0), CONSTRAINT ck_corporate_expense_status CHECK (status IN ('Pending Manager', 'Pending Finance', 'Approved', 'Rejected')))",
        )
        with db.engine.begin() as connection:
            for table in (
                "corporate_expense_approvals",
                "corporate_audit_logs",
                "corporate_expenses",
                "corporate_memberships",
                "corporate_departments",
                "corporate_organizations",
            ):
                connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
            for statement in legacy_schema:
                connection.execute(text(statement))

        runner = app.test_cli_runner()
        first = runner.invoke(args=["migrate-corporate-workflows"])
        assert first.exit_code == 0, first.output
        second = runner.invoke(args=["migrate-corporate-workflows"])
        assert second.exit_code == 0, second.output

        columns = {
            table: {column["name"] for column in inspect(db.engine).get_columns(table)}
            for table in (
                "corporate_organizations",
                "corporate_departments",
                "corporate_memberships",
                "corporate_expenses",
            )
        }
        assert {"organization_email", "contact_phone", "address", "status", "joining_enabled"} <= columns["corporate_organizations"]
        assert {"manager_id", "status"} <= columns["corporate_departments"]
        assert {"membership_status", "joined_at"} <= columns["corporate_memberships"]
        assert {"receipt_path", "receipt_filename", "rejection_reason", "paid_at", "updated_at"} <= columns["corporate_expenses"]
        assert {"corporate_expense_approvals", "corporate_audit_logs"} <= set(inspect(db.engine).get_table_names())
        assert db.session.get(User, user_id).email == "preserved@workflow.example"
        preserved_expense = db.session.get(Expense, expense_id)
        assert preserved_expense.amount == Decimal("23.50")
        assert preserved_expense.vendor == "Local Store"
