from datetime import datetime, timezone

from sqlalchemy import Index, Numeric, UniqueConstraint

from extensions import db


class SyntheticFinanceSnapshot(db.Model):
    __tablename__ = "synthetic_finance_snapshots"
    __table_args__ = (
        UniqueConstraint("source_record_id", name="uq_synthetic_snapshot_source_record"),
        Index("ix_synthetic_snapshot_employment", "employment_status"),
        Index("ix_synthetic_snapshot_region", "region"),
    )

    snapshot_id = db.Column(db.Integer, primary_key=True)
    source_record_id = db.Column(db.String(40), nullable=False)
    source_dataset_sha256 = db.Column(db.String(64), nullable=False)
    source_currency = db.Column(db.String(3), nullable=False, default="USD")
    target_currency = db.Column(db.String(3), nullable=False, default="INR")
    usd_inr_rate = db.Column(Numeric(10, 4), nullable=False)

    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(30), nullable=False)
    education_level = db.Column(db.String(80), nullable=False)
    employment_status = db.Column(db.String(50), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)
    monthly_income_inr = db.Column(Numeric(14, 2), nullable=False)
    monthly_expenses_inr = db.Column(Numeric(14, 2), nullable=False)
    savings_inr = db.Column(Numeric(14, 2), nullable=False)
    has_loan = db.Column(db.Boolean, nullable=False)
    loan_type = db.Column(db.String(50))
    loan_amount_inr = db.Column(Numeric(14, 2), nullable=False)
    loan_term_months = db.Column(db.Integer, nullable=False)
    monthly_emi_inr = db.Column(Numeric(14, 2), nullable=False)
    loan_interest_rate_pct = db.Column(Numeric(7, 3), nullable=False)
    debt_to_income_ratio = db.Column(Numeric(9, 4), nullable=False)
    credit_score = db.Column(db.Integer, nullable=False)
    savings_to_income_ratio = db.Column(Numeric(9, 4), nullable=False)
    region = db.Column(db.String(80), nullable=False)
    record_date = db.Column(db.Date, nullable=False)
    imported_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
