from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, Numeric

from extensions import db


class Expense(db.Model):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_positive_amount"),
        Index("ix_expenses_user_date", "user_id", "date"),
        Index("ix_expenses_user_category", "user_id", "category_id"),
        Index("ix_expenses_user_amount", "user_id", "amount"),
    )

    expense_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.category_id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = db.Column(Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)
    payment_method = db.Column(db.String(80), nullable=True)
    vendor = db.Column(db.String(160), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="expenses")
    category = db.relationship("Category", back_populates="expenses")

    def to_dict(self):
        return {
            "expense_id": self.expense_id,
            "user_id": self.user_id,
            "category_id": self.category_id,
            "category_name": self.category.category_name,
            "amount": format(self.amount, ".2f"),
            "date": self.date.isoformat(),
            "description": self.description,
            "payment_method": self.payment_method,
            "vendor": self.vendor,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }