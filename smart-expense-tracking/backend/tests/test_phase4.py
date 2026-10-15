import pytest

from app import create_app
from extensions import db
from models import Budget, Category, Expense, Income


class TestConfig:
    TESTING = True
    SECRET_KEY = "phase-four-test-secret"
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
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def authenticated(client, email="phase4@example.com"):
    register = client.post(
        "/api/auth/register",
        json={"name": "Phase Four", "email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    assert register.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    assert login.status_code == 200
    return login.json["data"]["csrf_token"]


def add_category(app, name="Food"):
    with app.app_context():
        category = Category(category_name=name)
        db.session.add(category)
        db.session.commit()
        return category.category_id


def post_income(client, token, **overrides):
    payload = {"source": "Salary", "amount": "1000.00", "date": "2026-01-31", "description": "Monthly pay"}
    payload.update(overrides)
    return client.post("/api/income", json=payload, headers={"X-CSRF-Token": token})


def post_expense(client, token, category_id, amount, expense_date):
    return client.post(
        "/api/expenses",
        json={"category_id": category_id, "amount": amount, "date": expense_date},
        headers={"X-CSRF-Token": token},
    )


def test_income_crud_persists_and_filters_inclusive_date_boundaries(client):
    token = authenticated(client)
    first = post_income(client, token)
    second = post_income(client, token, source="Bonus", amount="250.00", date="2026-02-01")
    assert first.status_code == second.status_code == 201

    filtered = client.get("/api/income?start_date=2026-01-31&end_date=2026-02-01&sort=oldest")
    assert [row["date"] for row in filtered.json["data"]["incomes"]] == ["2026-01-31", "2026-02-01"]
    assert filtered.json["data"]["total_amount"] == "1250.00"

    income_id = first.json["data"]["income"]["income_id"]
    updated = client.put(
        f"/api/income/{income_id}",
        json={"amount": "1200.50", "description": "Updated pay"},
        headers={"X-CSRF-Token": token},
    )
    assert updated.status_code == 200
    assert updated.json["data"]["income"]["amount"] == "1200.50"
    assert client.get(f"/api/income/{income_id}").status_code == 200
    assert client.delete(f"/api/income/{income_id}", headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get(f"/api/income/{income_id}").status_code == 404
    with client.application.app_context():
        assert Income.query.count() == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [("source", "  "), ("source", "x" * 121), ("amount", "0"), ("amount", "1.001"), ("date", "2026-02-30")],
)
def test_income_rejects_invalid_backend_values(client, field, value):
    token = authenticated(client)
    response = post_income(client, token, **{field: value})
    assert response.status_code == 400
    assert field in response.json["errors"]


def test_income_filter_rejects_invalid_or_reversed_dates(client):
    authenticated(client)
    assert client.get("/api/income?start_date=2026-02-30").status_code == 400
    assert client.get("/api/income?start_date=2026-02-02&end_date=2026-02-01").status_code == 400


def test_income_records_are_private_and_api_requires_authentication(client):
    assert client.get("/api/income").status_code == 401
    owner_token = authenticated(client)
    record = post_income(client, owner_token)
    income_id = record.json["data"]["income"]["income_id"]
    other_client = client.application.test_client()
    authenticated(other_client, "other-phase4@example.com")
    assert other_client.get(f"/api/income/{income_id}").status_code == 404
    assert other_client.put(
        f"/api/income/{income_id}", json={"source": "Changed"}, headers=csrf_headers(other_client)
    ).status_code == 404
    assert other_client.delete(f"/api/income/{income_id}", headers=csrf_headers(other_client)).status_code == 404


def test_budget_crud_unique_overall_and_category_periods(client, app):
    token = authenticated(client)
    category_id = add_category(app)
    overall = client.post(
        "/api/budgets", json={"amount": "200.00", "month": 1, "year": 2026}, headers={"X-CSRF-Token": token}
    )
    category = client.post(
        "/api/budgets",
        json={"amount": "100.00", "category_id": category_id, "month": 1, "year": 2026},
        headers={"X-CSRF-Token": token},
    )
    assert overall.status_code == category.status_code == 201
    duplicate_overall = client.post(
        "/api/budgets", json={"amount": "300.00", "month": 1, "year": 2026}, headers={"X-CSRF-Token": token}
    )
    duplicate_category = client.post(
        "/api/budgets",
        json={"amount": "300.00", "category_id": category_id, "month": 1, "year": 2026},
        headers={"X-CSRF-Token": token},
    )
    assert duplicate_overall.status_code == duplicate_category.status_code == 409

    budget_id = category.json["data"]["budget"]["budget_id"]
    updated = client.put(
        f"/api/budgets/{budget_id}",
        json={"amount": "150.25"},
        headers={"X-CSRF-Token": token},
    )
    assert updated.status_code == 200
    assert updated.json["data"]["budget"]["amount"] == "150.25"
    assert client.get("/api/budgets?month=2&year=2026").json["data"]["budgets"] == []
    assert client.delete(f"/api/budgets/{budget_id}", headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get(f"/api/budgets/{budget_id}").status_code == 404
    with app.app_context():
        assert Budget.query.count() == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"amount": "-1.00", "month": 1, "year": 2026},
        {"amount": "1.001", "month": 1, "year": 2026},
        {"amount": "1.00", "month": 13, "year": 2026},
        {"amount": "1.00", "month": 1, "year": 1899},
    ],
)
def test_budget_rejects_invalid_amount_or_period(client, payload):
    token = authenticated(client)
    response = client.post("/api/budgets", json=payload, headers={"X-CSRF-Token": token})
    assert response.status_code == 400
    assert response.json["errors"]


def test_budget_spending_is_decimal_scoped_to_period_and_category(client, app):
    token = authenticated(client)
    food_id = add_category(app, "Food")
    transit_id = add_category(app, "Transit")
    budget_response = client.post(
        "/api/budgets",
        json={"amount": "20.00", "category_id": food_id, "month": 1, "year": 2026},
        headers={"X-CSRF-Token": token},
    )
    budget_id = budget_response.json["data"]["budget"]["budget_id"]
    assert post_expense(client, token, food_id, "12.35", "2026-01-31").status_code == 201
    assert post_expense(client, token, food_id, "12.35", "2026-02-01").status_code == 201
    assert post_expense(client, token, transit_id, "9.99", "2026-01-15").status_code == 201
    january = client.get(f"/api/budgets/{budget_id}").json["data"]["budget"]
    assert january["spent_amount"] == "12.35"
    assert january["remaining_amount"] == "7.65"
    assert january["utilization_percentage"] == "61.75"
    assert january["over_budget"] is False


def test_overall_budget_includes_all_user_spending_and_reports_overspend(client, app):
    token = authenticated(client)
    category_id = add_category(app)
    created = client.post(
        "/api/budgets",
        json={"amount": "10.00", "month": 1, "year": 2026},
        headers={"X-CSRF-Token": token},
    )
    budget_id = created.json["data"]["budget"]["budget_id"]
    assert post_expense(client, token, category_id, "15.50", "2026-01-20").status_code == 201
    response = client.get(f"/api/budgets/{budget_id}")
    budget = response.json["data"]["budget"]
    assert budget["spent_amount"] == "15.50"
    assert budget["remaining_amount"] == "-5.50"
    assert budget["utilization_percentage"] == "155.00"
    assert budget["over_budget"] is True


def test_budgets_are_private_and_period_filter_requires_month_and_year(client):
    assert client.get("/api/budgets").status_code == 401
    token = authenticated(client)
    created = client.post(
        "/api/budgets",
        json={"amount": "25.00", "month": 1, "year": 2026},
        headers={"X-CSRF-Token": token},
    )
    budget_id = created.json["data"]["budget"]["budget_id"]
    other_client = client.application.test_client()
    other_token = authenticated(other_client, "budget-other@example.com")
    assert other_client.get(f"/api/budgets/{budget_id}").status_code == 404
    assert other_client.put(
        f"/api/budgets/{budget_id}", json={"amount": "30.00"}, headers={"X-CSRF-Token": other_token}
    ).status_code == 404
    assert other_client.delete(f"/api/budgets/{budget_id}", headers={"X-CSRF-Token": other_token}).status_code == 404
    assert client.get("/api/budgets?month=1").status_code == 400
