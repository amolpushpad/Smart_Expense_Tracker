import csv
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest

from app import create_app
from extensions import db
from models import Budget, Category, Expense, Income, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "analytics-test-secret"
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
    return {"X-CSRF-Token": client.get("/api/auth/csrf").json["data"]["csrf_token"]}


def register_and_login(client, email):
    client.post(
        "/api/auth/register",
        json={"name": "Analytics User", "email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    return response.json["data"]["csrf_token"]


def seed_cross_year_data(app, email="analytics@example.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).one()
        food = Category(category_name="Food")
        travel = Category(category_name="Travel")
        db.session.add_all([food, travel])
        db.session.flush()
        db.session.add_all([
            Expense(user_id=user.user_id, category_id=food.category_id, amount="10.25", date=date(2025, 12, 29), description="Monday lunch"),
            Income(user_id=user.user_id, source="Wages", amount="100.00", date=date(2025, 12, 31), description="December wages"),
            Expense(user_id=user.user_id, category_id=travel.category_id, amount="20.00", date=date(2026, 1, 1), description="New year trip"),
            Income(user_id=user.user_id, source="Gift", amount="50.00", date=date(2026, 1, 4), description="January gift"),
            Expense(user_id=user.user_id, category_id=food.category_id, amount="5.00", date=date(2026, 1, 4), description="Sunday dinner"),
            Expense(user_id=user.user_id, category_id=food.category_id, amount="40.00", date=date(2026, 2, 1), description="February food"),
            Budget(user_id=user.user_id, category_id=None, amount="40.00", month=1, year=2026),
        ])
        db.session.commit()


def test_weekly_analytics_uses_monday_sunday_and_compares_previous_week(client, app):
    register_and_login(client, "analytics@example.com")
    seed_cross_year_data(app)

    response = client.get("/api/analytics?period=weekly&date=2026-01-04")

    assert response.status_code == 200
    data = response.json["data"]
    assert data["period"]["start_date"] == "2025-12-29"
    assert data["period"]["end_date"] == "2026-01-04"
    assert data["period"]["week_starts_on"] == "Monday"
    assert data["summary"]["total_income"] == "150.00"
    assert data["summary"]["total_expenses"] == "35.25"
    assert data["summary"]["savings"] == "114.75"
    assert data["previous_period"]["start_date"] == "2025-12-22"
    assert data["highest_spending_category"]["category_name"] == "Travel"
    assert data["largest_transaction"]["amount"] == "100.00"
    assert data["series"]["granularity"] == "day"
    assert len(data["series"]["items"]) == 7
    assert data["series"]["items"][0]["date"] == "2025-12-29"


def test_monthly_analytics_handles_year_boundary_and_budget_totals(client, app):
    register_and_login(client, "analytics@example.com")
    seed_cross_year_data(app)

    january = client.get("/api/analytics?period=monthly&month=1&year=2026")
    assert january.status_code == 200
    data = january.json["data"]
    assert data["period"]["start_date"] == "2026-01-01"
    assert data["period"]["end_date"] == "2026-01-31"
    assert data["summary"]["total_income"] == "50.00"
    assert data["summary"]["total_expenses"] == "25.00"
    assert data["previous_period"]["start_date"] == "2025-12-01"
    assert data["previous_period"]["end_date"] == "2025-12-31"
    assert data["budget"]["monthly_budget"] == "40.00"
    assert data["budget"]["remaining_budget"] == "15.00"
    assert data["budget"]["budget_utilization"] == "62.50"
    assert [(item["category_name"], item["amount"]) for item in data["categories"]] == [
        ("Travel", "20.00"),
        ("Food", "5.00"),
    ]

    december = client.get("/api/analytics?period=monthly&month=12&year=2025")
    assert december.status_code == 200
    assert december.json["data"]["summary"]["total_income"] == "100.00"
    assert december.json["data"]["summary"]["total_expenses"] == "10.25"
    assert december.json["data"]["previous_period"]["start_date"] == "2025-11-01"


def test_custom_date_range_is_inclusive_and_series_scales_by_month(client, app):
    register_and_login(client, "analytics@example.com")
    seed_cross_year_data(app)

    response = client.get("/api/analytics?period=custom&start_date=2025-12-31&end_date=2026-01-01")
    data = response.json["data"]
    assert response.status_code == 200
    assert data["summary"]["total_income"] == "100.00"
    assert data["summary"]["total_expenses"] == "20.00"
    assert data["budget"] is None
    assert data["period"]["start_date"] == "2025-12-31"
    assert data["period"]["end_date"] == "2026-01-01"

    long_range = client.get("/api/analytics?period=custom&start_date=2025-12-01&end_date=2026-02-28")
    assert long_range.status_code == 200
    assert long_range.json["data"]["series"]["granularity"] == "month"
    assert [item["label"] for item in long_range.json["data"]["series"]["items"]] == [
        "Dec 2025", "Jan 2026", "Feb 2026"
    ]


@pytest.mark.parametrize(
    "query",
    [
        "period=weekly&date=2026-02-30",
        "period=monthly&month=13&year=2026",
        "period=monthly&month=2&year=1899",
        "period=custom&start_date=2026-03-01&end_date=2026-02-28",
        "period=custom&start_date=not-a-date&end_date=2026-02-28",
        "period=other",
    ],
)
def test_analytics_rejects_invalid_date_parameters(client, query):
    register_and_login(client, "invalid-analytics@example.com")
    assert client.get(f"/api/analytics?{query}").status_code == 400


def test_empty_period_returns_zero_totals_and_empty_categories(client):
    register_and_login(client, "empty-analytics@example.com")
    response = client.get("/api/analytics?period=weekly&date=2026-01-05")

    assert response.status_code == 200
    report = response.json["data"]
    assert report["summary"]["total_income"] == "0.00"
    assert report["summary"]["total_expenses"] == "0.00"
    assert report["summary"]["savings"] == "0.00"
    assert report["categories"] == []
    assert report["largest_transaction"] is None
    assert report["series"]["items"][0]["date"] == "2026-01-05"
    assert report["series"]["items"][0]["income"] == "0.00"


def test_csv_export_matches_report_totals_and_includes_filtered_transactions(client, app):
    register_and_login(client, "analytics@example.com")
    seed_cross_year_data(app)

    response = client.get("/api/analytics/export.csv?period=weekly&date=2026-01-04")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    rows = list(csv.DictReader(StringIO(response.get_data(as_text=True).lstrip("\ufeff"))))
    transaction_rows = [row for row in rows if row["record_type"] != "summary"]
    summary_row = next(row for row in rows if row["record_type"] == "summary")
    assert len(transaction_rows) == 5
    assert sum((Decimal(row["income"]) for row in transaction_rows), Decimal("0.00")) == Decimal("150.00")
    assert sum((Decimal(row["expense"]) for row in transaction_rows), Decimal("0.00")) == Decimal("35.25")
    assert summary_row["total_income"] == "150.00"
    assert summary_row["total_expenses"] == "35.25"
    assert summary_row["savings"] == "114.75"
    assert all(row["period_start"] == "2025-12-29" for row in rows)


def test_csv_export_escapes_spreadsheet_formulas(client, app):
    register_and_login(client, "csv-injection@example.com")
    with app.app_context():
        user = User.query.filter_by(email="csv-injection@example.com").one()
        category = Category(category_name="Formula")
        db.session.add(category)
        db.session.flush()
        db.session.add(Expense(
            user_id=user.user_id,
            category_id=category.category_id,
            amount="1.00",
            date=date(2026, 1, 5),
            description="  =HYPERLINK(\"https://example.invalid\")",
        ))
        db.session.commit()

    response = client.get("/api/analytics/export.csv?period=weekly&date=2026-01-05")
    rows = list(csv.DictReader(StringIO(response.get_data(as_text=True).lstrip("\ufeff"))))
    assert rows[0]["description"].startswith("'  =")


def test_analytics_and_csv_are_authenticated_and_user_scoped(client, app):
    assert client.get("/api/analytics").status_code == 401
    assert client.get("/api/analytics/export.csv").status_code == 401
    register_and_login(client, "analytics@example.com")
    seed_cross_year_data(app)

    other = app.test_client()
    register_and_login(other, "different-analytics@example.com")
    report = other.get("/api/analytics?period=weekly&date=2026-01-04")
    exported = other.get("/api/analytics/export.csv?period=weekly&date=2026-01-04")
    assert report.status_code == 200
    assert report.json["data"]["summary"]["total_income"] == "0.00"
    assert report.json["data"]["summary"]["total_expenses"] == "0.00"
    rows = list(csv.DictReader(StringIO(exported.get_data(as_text=True).lstrip("\ufeff"))))
    assert [row for row in rows if row["record_type"] != "summary"] == []
