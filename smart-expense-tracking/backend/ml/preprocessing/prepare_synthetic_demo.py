"""Create a privacy-minimized aggregate demo from the provided synthetic CSV."""
import argparse
import json
import math
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "user_id",
    "employment_status",
    "monthly_income_usd",
    "monthly_expenses_usd",
    "savings_usd",
    "has_loan",
    "loan_type",
    "record_date",
}
AMOUNT_COLUMNS = ("monthly_income_usd", "monthly_expenses_usd", "savings_usd")
EXPECTED_LOAN_VALUES = {"Yes", "No"}


def build_demo_summary(csv_path):
    """Validate the snapshot dataset and return only non-identifying aggregates."""
    frame = pd.read_csv(csv_path)
    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing_columns)}")
    if frame.empty:
        raise ValueError("Dataset contains no records.")
    if frame["user_id"].isna().any() or frame["user_id"].duplicated().any():
        raise ValueError("Expected one non-empty snapshot per unique synthetic user.")
    if frame["employment_status"].isna().any():
        raise ValueError("Employment status is required for every snapshot.")
    if not frame["has_loan"].isin(EXPECTED_LOAN_VALUES).all():
        raise ValueError("Loan status must contain only Yes or No.")

    for column in AMOUNT_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        values = frame[column].tolist()
        if any(pd.isna(value) or not math.isfinite(float(value)) or value < 0 for value in values):
            raise ValueError(f"{column} must contain finite, non-negative amounts.")

    dates = pd.to_datetime(frame["record_date"], format="%Y-%m-%d", errors="coerce")
    if dates.isna().any():
        raise ValueError("record_date must contain valid YYYY-MM-DD dates.")

    employment = (
        frame.groupby("employment_status", sort=True)
        .agg(
            records=("user_id", "count"),
            average_monthly_income_usd=("monthly_income_usd", "mean"),
            average_monthly_expenses_usd=("monthly_expenses_usd", "mean"),
            median_monthly_expenses_usd=("monthly_expenses_usd", "median"),
            average_savings_usd=("savings_usd", "mean"),
        )
        .reset_index()
    )
    loan_counts = frame["has_loan"].value_counts()
    loan_types = frame["loan_type"].fillna("No loan").value_counts().sort_index()

    def amount(value):
        return round(float(value), 2)

    total = len(frame)
    return {
        "dataset": {
            "name": "Synthetic Personal Finance Dataset",
            "kind": "synthetic_cross_sectional_user_snapshots",
            "currency": "USD",
            "record_count": total,
            "column_count": len(frame.columns),
            "snapshot_date_range": {
                "start": dates.min().date().isoformat(),
                "end": dates.max().date().isoformat(),
            },
            "exact_duplicate_rows": int(frame.duplicated().sum()),
            "duplicate_user_ids": int(frame["user_id"].duplicated().sum()),
            "note": (
                "Synthetic aggregate profile snapshots; not transaction history, "
                "not real user data, and not a forecast."
            ),
        },
        "overview": {
            "synthetic_profiles": total,
            "average_monthly_income_usd": amount(frame["monthly_income_usd"].mean()),
            "average_monthly_expenses_usd": amount(frame["monthly_expenses_usd"].mean()),
            "median_monthly_expenses_usd": amount(frame["monthly_expenses_usd"].median()),
            "average_savings_usd": amount(frame["savings_usd"].mean()),
            "profiles_with_loan": int(loan_counts.get("Yes", 0)),
            "profiles_with_loan_percent": amount(100 * loan_counts.get("Yes", 0) / total),
        },
        "employment_groups": [
            {
                "employment_status": row.employment_status,
                "records": int(row.records),
                "average_monthly_income_usd": amount(row.average_monthly_income_usd),
                "average_monthly_expenses_usd": amount(row.average_monthly_expenses_usd),
                "median_monthly_expenses_usd": amount(row.median_monthly_expenses_usd),
                "average_savings_usd": amount(row.average_savings_usd),
            }
            for row in employment.itertuples(index=False)
        ],
        "loan_types": [
            {"loan_type": str(name), "records": int(count)}
            for name, count in loan_types.items()
        ],
    }


def main():
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Path to the user-provided synthetic CSV.")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root / "frontend" / "src" / "data" / "synthetic-finance-demo.json",
        help="Output JSON path (defaults to the frontend's aggregate demo data).",
    )
    args = parser.parse_args()
    summary = build_demo_summary(args.csv_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {summary['dataset']['record_count']} synthetic snapshots as aggregate demo data to {args.output}.")


if __name__ == "__main__":
    main()
