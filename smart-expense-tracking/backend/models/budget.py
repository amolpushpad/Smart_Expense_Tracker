from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Computed, Numeric, UniqueConstraint

from extensions import db


class Budget(db.Model):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_budgets_positive_amount"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_budgets_valid_month"),
        CheckConstraint("year >= 1900 AND year <= 9999", name="ck_budgets_valid_year"),
        UniqueConstraint("user_id", "category_scope", "month", "year", name="uq_budgets_user_category_period"),
    )

    budget_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.category_id", ondelete="RESTRICT"), nullable=True)
    category_scope = db.Column(db.Integer, Computed("coalesce(category_id, 0)", persisted=True), nullable=False)
    amount = db.Column(Numeric(10, 2), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    category = db.relationship("Category")

    def to_dict(self, spent_amount):
        amount = self.amount
        spent = spent_amount
        remaining = amount - spent
        utilization = (spent / amount * 100) if amount > 0 else None
        return {
            "budget_id": self.budget_id,
            "user_id": self.user_id,
            "category_id": self.category_id,
            "category_name": self.category.category_name if self.category else None,
            "amount": format(amount, ".2f"),
            "month": self.month,
            "year": self.year,
            "spent_amount": format(spent, ".2f"),
            "remaining_amount": format(remaining, ".2f"),
            "utilization_percentage": format(utilization, ".2f") if utilization is not None else None,
            "over_budget": remaining < 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
