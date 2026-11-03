import csv
from datetime import date
from decimal import Decimal

import pytest

from app import create_app
from extensions import db
from ml.import_synthetic_snapshots import import_snapshot_csv
from models import Expense, SyntheticFinanceSnapshot


class TestConfig:
    TESTING = True
    SECRET_KEY = "synthetic-import-test-secret"
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


def _write_csv(path, rows=None):
    rows = rows or [{
        "user_id": "SYN-001",
        "age": 31,
        "gender": "Other",
        "education_level": "College",
        "employment_status": "Employed",
        "job_title": "Analyst",
        "monthly_income_usd": "1000.25",
        "monthly_expenses_usd": "12.34",
        "savings_usd": "99.99",
        "has_loan": "No",
        "loan_type": "None",
        "loan_amount_usd": "0",
        "loan_term_months": "0",
        "monthly_emi_usd": "0",
        "loan_interest_rate_pct": "0",
        "debt_to_income_ratio": "0",
        "credit_score": "700",
        "savings_to_income_ratio": "0.1",
        "region": "Other",
        "record_date": "2024-01-15",
    }]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_import_converts_currency_and_is_idempotent_without_creating_transactions(app, tmp_path):
    source = _write_csv(tmp_path / "synthetic.csv")
    with app.app_context():
        result = import_snapshot_csv(source, Decimal("95"))

        assert result["imported"] == 1
        snapshot = SyntheticFinanceSnapshot.query.one()
        assert snapshot.monthly_income_inr == Decimal("95023.75")
        assert snapshot.monthly_expenses_inr == Decimal("1172.30")
        assert snapshot.savings_inr == Decimal("9499.05")
        assert snapshot.target_currency == "INR"
        assert snapshot.usd_inr_rate == Decimal("95.0000")
        assert snapshot.record_date == date(2024, 1, 15)
        assert Expense.query.count() == 0

        repeated = import_snapshot_csv(source, Decimal("95"))
        assert repeated["already_imported"] is True
        assert SyntheticFinanceSnapshot.query.count() == 1


def test_import_refuses_a_different_rate_or_source_without_mutating_data(app, tmp_path):
    source = _write_csv(tmp_path / "synthetic.csv")
    with app.app_context():
        import_snapshot_csv(source, Decimal("95"))

        with pytest.raises(ValueError, match="different dataset or conversion rate"):
            import_snapshot_csv(source, Decimal("90"))

        assert SyntheticFinanceSnapshot.query.one().monthly_expenses_inr == Decimal("1172.30")
        assert Expense.query.count() == 0


def test_import_rejects_duplicate_snapshot_ids_before_database_writes(app, tmp_path):
    first = {
        "user_id": "SYN-001",
        "age": "31",
        "gender": "Other",
        "education_level": "College",
        "employment_status": "Employed",
        "job_title": "Analyst",
        "monthly_income_usd": "1000",
        "monthly_expenses_usd": "500",
        "savings_usd": "100",
        "has_loan": "No",
        "loan_type": "",
        "loan_amount_usd": "0",
        "loan_term_months": "0",
        "monthly_emi_usd": "0",
        "loan_interest_rate_pct": "0",
        "debt_to_income_ratio": "0",
        "credit_score": "700",
        "savings_to_income_ratio": "0.1",
        "region": "Other",
        "record_date": "2024-01-15",
    }
    source = _write_csv(tmp_path / "duplicates.csv", [first, dict(first)])
    with app.app_context():
        with pytest.raises(ValueError, match="duplicate synthetic user_id"):
            import_snapshot_csv(source, Decimal("95"))
        assert SyntheticFinanceSnapshot.query.count() == 0
