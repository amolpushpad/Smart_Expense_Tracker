from datetime import date
from decimal import Decimal

import pytest

from app import create_app
from extensions import db
from models import Category, Expense, SyntheticFinanceSnapshot, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "synthetic-demo-test-secret"
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


def _insert_snapshots(count=120):
    snapshots = []
    for index in range(count):
        snapshots.append(SyntheticFinanceSnapshot(
            source_record_id=f"SYN{index:05d}",
            source_dataset_sha256="a" * 64,
            source_currency="USD",
            target_currency="INR",
            usd_inr_rate=Decimal("95.0000"),
            age=20 + index % 45,
            gender="Other",
            education_level="College",
            employment_status=("Employed", "Self-employed")[index % 2],
            job_title="Analyst",
            monthly_income_inr=Decimal(30000 + index * 100),
            monthly_expenses_inr=Decimal(18000 + index * 50),
            savings_inr=Decimal(50000 + index * 1000),
            has_loan=index % 2 == 0,
            loan_type="Car" if index % 2 == 0 else None,
            loan_amount_inr=Decimal("190000.00") if index % 2 == 0 else Decimal("0.00"),
            loan_term_months=36 if index % 2 == 0 else 0,
            monthly_emi_inr=Decimal("9500.00") if index % 2 == 0 else Decimal("0.00"),
            loan_interest_rate_pct=Decimal("8.5") if index % 2 == 0 else Decimal("0"),
            debt_to_income_ratio=Decimal("0.25") if index % 2 == 0 else Decimal("0"),
            credit_score=600 + index % 200,
            savings_to_income_ratio=Decimal("1.5"),
            region="North America",
            record_date=date(2024, 1, 1),
        ))
    db.session.add_all(snapshots)
    db.session.commit()


def test_demo_analytics_are_isolated_and_use_inr(client, app):
    with app.app_context():
        _insert_snapshots(2)
        # A normal user expense remains outside the demo snapshot aggregates.
        user = User(name="Real user", email="real@example.com", password_hash="not-used")
        category = Category(category_name="Food")
        db.session.add(category)
        db.session.flush()
        db.session.add(user)
        db.session.commit()
        expense = Expense(
            user_id=user.user_id,
            category_id=category.category_id,
            amount=Decimal("10.00"),
            date=date(2024, 1, 1),
        )
        db.session.add(expense)
        db.session.commit()

    response = client.get("/api/demo/analytics")

    assert response.status_code == 200
    data = response.json["data"]
    assert data["dataset"]["currency"] == "INR"
    assert data["dataset"]["usd_inr_rate"] == "95.0000"
    assert data["overview"]["synthetic_profiles"] == 2
    assert data["overview"]["average_monthly_income_inr"] == 30050.0
    assert "SYN00000" not in response.get_data(as_text=True)
    assert "real@example.com" not in response.get_data(as_text=True)


def test_model_evaluation_and_estimate_use_only_isolated_snapshots(client, app):
    with app.app_context():
        _insert_snapshots()

    evaluation_response = client.get("/api/demo/ml/evaluation")
    assert evaluation_response.status_code == 200
    evaluation = evaluation_response.json["data"]
    assert evaluation["training_records"] == 96
    assert evaluation["held_out_records"] == 24
    assert evaluation["currency"] == "INR"
    assert evaluation["reliable_for_personal_forecasts"] is False

    estimate_response = client.post("/api/demo/ml/estimate-monthly-expenses", json={
        "age": 31,
        "monthly_income_inr": 50000,
        "savings_inr": 80000,
        "employment_status": "Employed",
        "has_loan": False,
    })
    assert estimate_response.status_code == 200
    estimate = estimate_response.json["data"]
    assert estimate["currency"] == "INR"
    assert estimate["stored"] is False
    assert estimate["is_next_month_forecast"] is False
    assert estimate["estimate_monthly_expenses_inr"] >= 0


def test_synthetic_model_rejects_malformed_profiles(client):
    response = client.post("/api/demo/ml/estimate-monthly-expenses", json={
        "age": True,
        "monthly_income_inr": float("nan"),
        "savings_inr": -1,
        "employment_status": "",
        "has_loan": "No",
        "user_id": 1,
    })

    assert response.status_code == 400
    assert set(response.json["errors"]) == {
        "age", "monthly_income_inr", "savings_inr", "employment_status", "has_loan", "user_id",
    }


def test_synthetic_endpoints_are_explicit_when_data_is_not_imported(client):
    response = client.get("/api/demo/analytics")

    assert response.status_code == 503
    assert "import" in response.json["message"].lower()
