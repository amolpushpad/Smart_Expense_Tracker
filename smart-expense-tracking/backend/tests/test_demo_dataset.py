import pandas as pd
import pytest

from ml.preprocessing.prepare_synthetic_demo import build_demo_summary


def _write_dataset(path, **overrides):
    row = {
        "user_id": "SYN-001",
        "age": 31,
        "gender": "Other",
        "education_level": "College",
        "employment_status": "Employed",
        "job_title": "Analyst",
        "monthly_income_usd": 4000,
        "monthly_expenses_usd": 2500,
        "savings_usd": 10000,
        "has_loan": "No",
        "loan_type": None,
        "loan_amount_usd": 0,
        "loan_term_months": 0,
        "monthly_emi_usd": 0,
        "loan_interest_rate_pct": 0,
        "debt_to_income_ratio": 0,
        "credit_score": 700,
        "savings_to_income_ratio": 2.5,
        "region": "North America",
        "record_date": "2024-01-15",
    }
    row.update(overrides)
    pd.DataFrame([row]).to_csv(path, index=False)
    return path


def test_summary_contains_only_aggregates_and_explicit_synthetic_metadata(tmp_path):
    source = _write_dataset(tmp_path / "synthetic.csv")

    summary = build_demo_summary(source)

    assert summary["dataset"]["kind"] == "synthetic_cross_sectional_user_snapshots"
    assert summary["dataset"]["record_count"] == 1
    assert summary["overview"]["average_monthly_expenses_usd"] == 2500
    assert summary["employment_groups"][0]["employment_status"] == "Employed"
    assert "SYN-001" not in str(summary)
    assert "transaction history" in summary["dataset"]["note"]


def test_summary_aggregates_loan_and_employment_counts(tmp_path):
    source = tmp_path / "synthetic.csv"
    first = {
        "user_id": "SYN-001",
        "employment_status": "Employed",
        "monthly_income_usd": 4000,
        "monthly_expenses_usd": 2500,
        "savings_usd": 10000,
        "has_loan": "No",
        "loan_type": None,
        "record_date": "2024-01-15",
    }
    second = {**first, "user_id": "SYN-002", "has_loan": "Yes", "loan_type": "Car"}
    pd.DataFrame([first, second]).to_csv(source, index=False)

    summary = build_demo_summary(source)

    assert summary["overview"]["synthetic_profiles"] == 2
    assert summary["overview"]["profiles_with_loan"] == 1
    assert summary["overview"]["profiles_with_loan_percent"] == 50
    assert summary["employment_groups"][0]["records"] == 2


def test_invalid_duplicate_user_snapshots_are_rejected(tmp_path):
    source = tmp_path / "duplicates.csv"
    row = {
        "user_id": "SYN-001",
        "employment_status": "Employed",
        "monthly_income_usd": 4000,
        "monthly_expenses_usd": 2500,
        "savings_usd": 10000,
        "has_loan": "No",
        "loan_type": None,
        "record_date": "2024-01-15",
    }
    pd.DataFrame([row, row]).to_csv(source, index=False)

    with pytest.raises(ValueError, match="unique synthetic user"):
        build_demo_summary(source)


def test_invalid_dates_and_non_finite_amounts_are_rejected(tmp_path):
    invalid_date = _write_dataset(tmp_path / "invalid-date.csv", record_date="not-a-date")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_demo_summary(invalid_date)

    invalid_amount = _write_dataset(tmp_path / "invalid-amount.csv", monthly_expenses_usd=float("inf"))
    with pytest.raises(ValueError, match="finite, non-negative"):
        build_demo_summary(invalid_amount)
