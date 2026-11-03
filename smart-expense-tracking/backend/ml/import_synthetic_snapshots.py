"""Validated, isolated importer for the synthetic profile snapshot dataset."""
import csv
import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from extensions import db
from models import SyntheticFinanceSnapshot


AMOUNT_FIELDS = {
    "monthly_income_usd": "monthly_income_inr",
    "monthly_expenses_usd": "monthly_expenses_inr",
    "savings_usd": "savings_inr",
    "loan_amount_usd": "loan_amount_inr",
    "monthly_emi_usd": "monthly_emi_inr",
}
REQUIRED_FIELDS = {
    "user_id", "age", "gender", "education_level", "employment_status", "job_title",
    *AMOUNT_FIELDS.keys(), "has_loan", "loan_type", "loan_term_months",
    "loan_interest_rate_pct", "debt_to_income_ratio", "credit_score",
    "savings_to_income_ratio", "region", "record_date",
}
CENT = Decimal("0.01")


def _decimal(value, field, *, minimum=None):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field} must be a valid decimal number.") from None
    if not number.is_finite() or (minimum is not None and number < minimum):
        raise ValueError(f"{field} must be finite and at least {minimum}.")
    return number


def _currency_to_inr(value, rate, field):
    return (_decimal(value, field, minimum=Decimal("0")) * rate).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_snapshot_csv(csv_path, usd_inr_rate):
    path = Path(csv_path)
    if not path.is_file():
        raise ValueError(f"Dataset file does not exist: {path}")
    rate = _decimal(usd_inr_rate, "USD/INR rate", minimum=Decimal("0.0001"))
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("Dataset CSV is empty.")
        missing_fields = sorted(REQUIRED_FIELDS - set(reader.fieldnames))
        if missing_fields:
            raise ValueError(f"Dataset is missing required columns: {', '.join(missing_fields)}")
        records = []
        seen_ids = set()
        for line_number, row in enumerate(reader, start=2):
            source_id = (row.get("user_id") or "").strip()
            if not source_id or source_id in seen_ids:
                raise ValueError(f"Missing or duplicate synthetic user_id on CSV line {line_number}.")
            seen_ids.add(source_id)
            try:
                has_loan_value = row["has_loan"].strip()
                if has_loan_value not in {"Yes", "No"}:
                    raise ValueError("has_loan must be Yes or No.")
                raw_loan_type = (row.get("loan_type") or "").strip()
                loan_type = None if raw_loan_type.casefold() in {"", "none", "null", "nan", "na", "n/a"} else raw_loan_type
                if (has_loan_value == "No") != (loan_type is None):
                    raise ValueError("loan_type must be blank only when has_loan is No.")
                date_value = datetime.strptime(row["record_date"], "%Y-%m-%d").date()
                record = {
                    "source_record_id": source_id,
                    "source_dataset_sha256": source_hash,
                    "source_currency": "USD",
                    "target_currency": "INR",
                    "usd_inr_rate": rate,
                    "age": int(row["age"]),
                    "gender": row["gender"].strip(),
                    "education_level": row["education_level"].strip(),
                    "employment_status": row["employment_status"].strip(),
                    "job_title": row["job_title"].strip(),
                    "has_loan": has_loan_value == "Yes",
                    "loan_type": loan_type,
                    "loan_term_months": int(row["loan_term_months"]),
                    "loan_interest_rate_pct": _decimal(row["loan_interest_rate_pct"], "loan_interest_rate_pct", minimum=Decimal("0")),
                    "debt_to_income_ratio": _decimal(row["debt_to_income_ratio"], "debt_to_income_ratio", minimum=Decimal("0")),
                    "credit_score": int(row["credit_score"]),
                    "savings_to_income_ratio": _decimal(row["savings_to_income_ratio"], "savings_to_income_ratio", minimum=Decimal("0")),
                    "region": row["region"].strip(),
                    "record_date": date_value,
                }
                for source_field, target_field in AMOUNT_FIELDS.items():
                    record[target_field] = _currency_to_inr(row[source_field], rate, source_field)
                if (
                    not 18 <= record["age"] <= 120
                    or record["loan_term_months"] < 0
                    or not 300 <= record["credit_score"] <= 850
                    or any(not record[field] for field in ("gender", "education_level", "employment_status", "job_title", "region"))
                ):
                    raise ValueError("Profile contains invalid age, term, credit score, or empty required categories.")
            except (ValueError, InvalidOperation) as error:
                raise ValueError(f"Invalid dataset row on CSV line {line_number}: {error}") from error
            records.append(record)

    if not records:
        raise ValueError("Dataset CSV contains no profile snapshots.")
    return records, source_hash, rate


def import_snapshot_csv(csv_path, usd_inr_rate=Decimal("95")):
    """Create the isolated table and import once; identical imports are a no-op."""
    records, source_hash, rate = parse_snapshot_csv(csv_path, usd_inr_rate)
    SyntheticFinanceSnapshot.__table__.create(bind=db.engine, checkfirst=True)

    existing = SyntheticFinanceSnapshot.query.with_entities(
        SyntheticFinanceSnapshot.source_record_id,
        SyntheticFinanceSnapshot.source_dataset_sha256,
        SyntheticFinanceSnapshot.usd_inr_rate,
    ).all()
    existing_ids = {row.source_record_id for row in existing}
    incoming_ids = {row["source_record_id"] for row in records}
    if existing:
        if (
            existing_ids == incoming_ids
            and all(row.source_dataset_sha256 == source_hash and Decimal(row.usd_inr_rate) == rate for row in existing)
        ):
            return {"imported": 0, "records": len(records), "already_imported": True, "rate": str(rate)}
        raise ValueError(
            "The isolated snapshot table already contains a different dataset or conversion rate. "
            "No rows were changed; review the existing import before replacing it."
        )

    try:
        for start in range(0, len(records), 1000):
            db.session.execute(
                db.insert(SyntheticFinanceSnapshot),
                records[start:start + 1000],
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {"imported": len(records), "records": len(records), "already_imported": False, "rate": str(rate)}
