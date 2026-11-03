"""Aggregate analytics and cross-sectional ML for isolated synthetic snapshots."""
from collections import defaultdict
from decimal import Decimal
import math

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from models import SyntheticFinanceSnapshot

NUMERIC_FEATURES = ("age", "monthly_income_inr", "savings_inr")
CATEGORICAL_FEATURES = ("employment_status", "has_loan")
FEATURES = (*NUMERIC_FEATURES, *CATEGORICAL_FEATURES)
TARGET = "monthly_expenses_inr"
MODEL_VERSION = "synthetic-cross-sectional-expense-v1"
MINIMUM_TRAINING_RECORDS = 100
_model_cache = {}


def _amount(value):
    return round(float(value or 0), 2)


def _require_rows():
    rows = SyntheticFinanceSnapshot.query.order_by(SyntheticFinanceSnapshot.snapshot_id.asc()).all()
    if not rows:
        raise ValueError("No synthetic snapshots are imported. Run the isolated dataset import command first.")
    return rows


def synthetic_snapshot_analytics():
    rows = _require_rows()
    employment = defaultdict(list)
    loan_types = defaultdict(int)
    regions = defaultdict(int)
    incomes = []
    expenses = []
    savings = []
    loans = 0

    for row in rows:
        income = Decimal(row.monthly_income_inr)
        expense = Decimal(row.monthly_expenses_inr)
        saving = Decimal(row.savings_inr)
        incomes.append(income)
        expenses.append(expense)
        savings.append(saving)
        employment[row.employment_status].append((income, expense, saving))
        loan_types[row.loan_type or "No loan"] += 1
        regions[row.region] += 1
        loans += int(row.has_loan)

    def average(values):
        return _amount(sum(values, Decimal("0")) / len(values))

    employment_groups = []
    for name, items in sorted(employment.items()):
        group_incomes = [item[0] for item in items]
        group_expenses = [item[1] for item in items]
        group_savings = [item[2] for item in items]
        ordered_expenses = sorted(group_expenses)
        middle = len(ordered_expenses) // 2
        median = ordered_expenses[middle] if len(ordered_expenses) % 2 else (
            ordered_expenses[middle - 1] + ordered_expenses[middle]
        ) / 2
        employment_groups.append({
            "employment_status": name,
            "records": len(items),
            "average_monthly_income_inr": average(group_incomes),
            "average_monthly_expenses_inr": average(group_expenses),
            "median_monthly_expenses_inr": _amount(median),
            "average_savings_inr": average(group_savings),
        })

    dates = [row.record_date for row in rows]
    rate = {format(Decimal(row.usd_inr_rate), ".4f") for row in rows}
    if len(rate) != 1:
        raise ValueError("Imported snapshots contain inconsistent USD/INR conversion rates.")

    return {
        "dataset": {
            "kind": "synthetic_cross_sectional_user_snapshots",
            "currency": "INR",
            "source_currency": "USD",
            "usd_inr_rate": next(iter(rate)),
            "record_count": len(rows),
            "snapshot_date_range": {
                "start": min(dates).isoformat(),
                "end": max(dates).isoformat(),
            },
            "source_sha256": rows[0].source_dataset_sha256,
            "note": (
                "Synthetic profile snapshots, not transaction history or actual user data. "
                "Monthly totals are not forecasts."
            ),
        },
        "overview": {
            "synthetic_profiles": len(rows),
            "average_monthly_income_inr": average(incomes),
            "average_monthly_expenses_inr": average(expenses),
            "median_monthly_expenses_inr": _amount(
                (sorted(expenses)[(len(expenses) - 1) // 2] + sorted(expenses)[len(expenses) // 2]) / 2
            ),
            "average_savings_inr": average(savings),
            "profiles_with_loan": loans,
            "profiles_with_loan_percent": round(100 * loans / len(rows), 2),
        },
        "employment_groups": employment_groups,
        "loan_types": [
            {"loan_type": name, "records": count}
            for name, count in sorted(loan_types.items())
        ],
        "regions": [
            {"region": name, "records": count}
            for name, count in sorted(regions.items())
        ],
    }


def _model_and_evaluation():
    rows = _require_rows()
    dataset_key = (len(rows), rows[-1].snapshot_id, rows[0].source_dataset_sha256)
    if _model_cache.get("dataset_key") == dataset_key:
        return _model_cache["model"], _model_cache["evaluation"]
    if len(rows) < MINIMUM_TRAINING_RECORDS:
        raise ValueError(
            f"At least {MINIMUM_TRAINING_RECORDS} snapshots are required for an evaluation split; "
            f"only {len(rows)} are imported."
        )

    frame = pd.DataFrame([
        {
            "age": row.age,
            "monthly_income_inr": float(row.monthly_income_inr),
            "savings_inr": float(row.savings_inr),
            "employment_status": row.employment_status,
            "has_loan": "Yes" if row.has_loan else "No",
            TARGET: float(row.monthly_expenses_inr),
        }
        for row in rows
    ])
    x_train, x_test, y_train, y_test = train_test_split(
        frame[list(FEATURES)],
        frame[TARGET],
        test_size=0.2,
        random_state=42,
    )
    preprocessor = ColumnTransformer([
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median"))]), list(NUMERIC_FEATURES)),
        (
            "categorical",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore")),
            ]),
            list(CATEGORICAL_FEATURES),
        ),
    ])
    model = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(
            n_estimators=100,
            min_samples_leaf=8,
            random_state=42,
            n_jobs=-1,
        )),
    ])
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    baseline = np.full(len(y_test), float(y_train.mean()))
    model_mae = float(mean_absolute_error(y_test, predicted))
    baseline_mae = float(mean_absolute_error(y_test, baseline))
    model_rmse = math.sqrt(float(mean_squared_error(y_test, predicted)))
    baseline_rmse = math.sqrt(float(mean_squared_error(y_test, baseline)))
    evaluation = {
        "model_name": "RandomForestRegressor",
        "model_version": MODEL_VERSION,
        "task": "cross-sectional estimation of a reported monthly expense total",
        "currency": "INR",
        "training_records": len(x_train),
        "held_out_records": len(x_test),
        "split": "random 80/20 split across independent synthetic profile snapshots (random_state=42)",
        "metrics": {
            "mae_inr": round(model_mae, 2),
            "rmse_inr": round(model_rmse, 2),
            "r2": round(float(r2_score(y_test, predicted)), 4),
            "mean_baseline_mae_inr": round(baseline_mae, 2),
            "mean_baseline_rmse_inr": round(baseline_rmse, 2),
        },
        "beats_mean_baseline_mae": model_mae < baseline_mae,
        "reliable_for_personal_forecasts": False,
        "limitations": [
            "Training and evaluation data are synthetic, cross-sectional snapshots, not transaction history.",
            "The estimate is not a next-month forecast and is not trained on any signed-in user's records.",
            "A held-out score on this synthetic dataset does not establish real-world predictive value.",
        ],
    }
    _model_cache.clear()
    _model_cache.update({"dataset_key": dataset_key, "model": model, "evaluation": evaluation})
    return model, evaluation


def synthetic_model_evaluation():
    _, evaluation = _model_and_evaluation()
    return evaluation


def estimate_synthetic_monthly_expenses(profile):
    model, evaluation = _model_and_evaluation()
    values = {field: profile[field] for field in FEATURES}
    values["has_loan"] = "Yes" if values["has_loan"] else "No"
    estimate = max(0.0, float(model.predict(pd.DataFrame([values]))[0]))
    return {
        "estimate_monthly_expenses_inr": round(estimate, 2),
        "currency": "INR",
        "model": evaluation["model_name"],
        "model_version": evaluation["model_version"],
        "beats_mean_baseline_mae": evaluation["beats_mean_baseline_mae"],
        "evaluation": evaluation["metrics"],
        "is_synthetic_cross_sectional_estimate": True,
        "is_next_month_forecast": False,
        "stored": False,
        "notice": (
            "Experimental estimate based only on synthetic profile data. "
            "It is not a personal forecast or financial advice."
        ),
    }
