from datetime import date

import pytest

from app import create_app
from extensions import db
from models import Budget, Category, Expense, Income, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "dashboard-test-secret"
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


def register_and_login(client, email):
    client.post(
        "/api/auth/register",
        json={"name": "Dashboard User", "email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    return response.json["data"]["csrf_token"]


def seed_finances(app, email="dashboard@example.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).one()
        food = Category.query.filter_by(category_name="Food").first()
        if not food:
            food = Category(category_name="Food")
            db.session.add(food)
            db.session.flush()
        other = Category(category_name="Travel")
        db.session.add(other)
        db.session.flush()
        db.session.add_all([
            Income(user_id=user.user_id, source="Salary", amount="3000.00", date=date(2026, 4, 1)),
            Income(user_id=user.user_id, source="Bonus", amount="500.00", date=date(2026, 3, 31)),
            Expense(user_id=user.user_id, category_id=food.category_id, amount="100.00", date=date(2026, 4, 1), description="Lunch"),
            Expense(user_id=user.user_id, category_id=food.category_id, amount="50.00", date=date(2026, 4, 30), description="Dinner"),
            Expense(user_id=user.user_id, category_id=other.category_id, amount="25.00", date=date(2026, 4, 15), description="Bus"),
            Expense(user_id=user.user_id, category_id=food.category_id, amount="20.00", date=date(2026, 5, 1), description="May meal"),
            Budget(user_id=user.user_id, category_id=None, amount="200.00", month=4, year=2026),
            Budget(user_id=user.user_id, category_id=food.category_id, amount="120.00", month=4, year=2026),
        ])
        db.session.commit()


def test_dashboard_summary_separates_lifetime_and_monthly_finances(client, app):
    register_and_login(client, "dashboard@example.com")
    seed_finances(app)

    response = client.get("/api/dashboard/summary?month=4&year=2026")

    assert response.status_code == 200
    summary = response.json["data"]["summary"]
    assert summary["total_income"] == "3500.00"
    assert summary["total_expenses"] == "195.00"
    assert summary["current_balance"] == "3305.00"
    assert summary["monthly_income"] == "3000.00"
    assert summary["monthly_expenses"] == "175.00"
    assert summary["monthly_budget"] == "200.00"
    assert summary["budget_utilization"] == "87.50"
    assert summary["remaining_budget"] == "25.00"
    assert summary["highest_spending_category"] == {"category_name": "Food", "amount": "150.00"}
    assert summary["period"] == {
        "month": 4,
        "year": 2026,
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
    }


def test_dashboard_handles_empty_data_and_zero_income(client):
    register_and_login(client, "empty-dashboard@example.com")
    summary = client.get("/api/dashboard/summary?month=1&year=2026").json["data"]["summary"]

    assert summary["total_income"] == "0.00"
    assert summary["current_balance"] == "0.00"
    assert summary["budget_utilization"] is None
    assert summary["savings_rate"] == "0.00"
    assert summary["highest_spending_category"] is None
    assert summary["average_daily_spending"] == "0.00"


def test_dashboard_category_budgets_do_not_count_unbudgeted_categories(client, app):
    register_and_login(client, "category-budget-dashboard@example.com")
    seed_finances(app, "category-budget-dashboard@example.com")
    with app.app_context():
        user = User.query.filter_by(email="category-budget-dashboard@example.com").one()
        Budget.query.filter_by(user_id=user.user_id, category_id=None).delete()
        db.session.commit()

    summary = client.get("/api/dashboard/summary?month=4&year=2026").json["data"]["summary"]
    assert summary["monthly_expenses"] == "175.00"
    assert summary["monthly_budget"] == "120.00"
    assert summary["budgeted_spending"] == "150.00"
    assert summary["budget_utilization"] == "125.00"
    assert summary["remaining_budget"] == "-30.00"


def test_dashboard_chart_endpoints_obey_period_and_return_real_records(client, app):
    register_and_login(client, "charts@example.com")
    seed_finances(app, "charts@example.com")

    trends = client.get("/api/dashboard/monthly-trends?month=4&year=2026")
    assert trends.status_code == 200
    months = trends.json["data"]["months"]
    assert len(months) == 6
    assert months[-1]["month"] == 4
    assert months[-1]["income"] == "3000.00"
    assert months[-1]["expenses"] == "175.00"

    categories = client.get("/api/dashboard/category-breakdown?month=4&year=2026")
    assert categories.status_code == 200
    assert [(row["category_name"], row["amount"]) for row in categories.json["data"]["categories"]] == [
        ("Food", "150.00"),
        ("Travel", "25.00"),
    ]

    budgets = client.get("/api/dashboard/budget-progress?month=4&year=2026")
    assert budgets.status_code == 200
    progress = budgets.json["data"]["budgets"]
    assert len(progress) == 2
    assert {budget["category_name"]: budget["spent_amount"] for budget in progress} == {
        None: "175.00",
        "Food": "150.00",
    }


def test_recent_transactions_are_combined_ordered_and_limited(client, app):
    register_and_login(client, "recent@example.com")
    seed_finances(app, "recent@example.com")

    response = client.get("/api/dashboard/recent-transactions?limit=3")
    records = response.json["data"]["transactions"]

    assert response.status_code == 200
    assert len(records) == 3
    assert [record["date"] for record in records] == ["2026-05-01", "2026-04-30", "2026-04-15"]
    assert records[0]["transaction_type"] == "expense"
    assert records[1]["category"] == "Food"
    assert records[2]["description"] == "Bus"


def test_dashboard_endpoints_require_authentication_and_validate_period(client):
    for endpoint in (
        "/api/dashboard/summary",
        "/api/dashboard/recent-transactions",
        "/api/dashboard/monthly-trends",
        "/api/dashboard/category-breakdown",
        "/api/dashboard/budget-progress",
    ):
        assert client.get(endpoint).status_code == 401

    register_and_login(client, "invalid-period@example.com")
    assert client.get("/api/dashboard/summary?month=13&year=2026").status_code == 400
    assert client.get("/api/dashboard/category-breakdown?month=4&year=1800").status_code == 400
    assert client.get("/api/dashboard/recent-transactions?limit=0").status_code == 400


def test_dashboard_queries_do_not_leak_other_users_records(client, app):
    register_and_login(client, "dashboard-owner@example.com")
    seed_finances(app, "dashboard-owner@example.com")

    other = app.test_client()
    register_and_login(other, "dashboard-other@example.com")
    summary = other.get("/api/dashboard/summary?month=4&year=2026").json["data"]["summary"]
    trends = other.get("/api/dashboard/monthly-trends?month=4&year=2026").json["data"]["months"]
    transactions = other.get("/api/dashboard/recent-transactions").json["data"]["transactions"]

    assert summary["total_income"] == "0.00"
    assert summary["total_expenses"] == "0.00"
    assert all(row["income"] == "0.00" and row["expenses"] == "0.00" for row in trends)
    assert transactions == []
