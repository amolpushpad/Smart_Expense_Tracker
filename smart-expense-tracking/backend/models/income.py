from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, Numeric

from extensions import db


class Income(db.Model):
    __tablename__ = "income"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_income_positive_amount"),
        Index("ix_income_user_date", "user_id", "date"),
    )

    income_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False, index=True)
    source = db.Column(db.String(120), nullable=False)
    amount = db.Column(Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "income_id": self.income_id,
            "user_id": self.user_id,
            "source": self.source,
            "amount": format(self.amount, ".2f"),
            "date": self.date.isoformat(),
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
