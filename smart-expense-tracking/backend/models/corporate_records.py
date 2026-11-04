from datetime import datetime, timezone

from sqlalchemy import Index

from extensions import db


def _now():
    return datetime.now(timezone.utc)


class CorporateExpenseApproval(db.Model):
    __tablename__ = "corporate_expense_approvals"

    approval_id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(
        db.Integer,
        db.ForeignKey("corporate_expenses.expense_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id = db.Column(
        db.Integer,
        db.ForeignKey("user.user_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    previous_status = db.Column(db.String(24))
    new_status = db.Column(db.String(24), nullable=False)
    comments = db.Column(db.String(500))
    action_date = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, index=True)

    expense = db.relationship("CorporateExpense", back_populates="approvals")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])

    def to_dict(self):
        return {
            "approval_id": self.approval_id,
            "expense_id": self.expense_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_name": self.reviewer.name if self.reviewer else None,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "comments": self.comments,
            "action_date": self.action_date.isoformat() if self.action_date else None,
        }


class CorporateAuditLog(db.Model):
    __tablename__ = "corporate_audit_logs"
    __table_args__ = (Index("ix_corporate_audit_org_created", "organization_id", "created_at"),)

    log_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("corporate_organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="SET NULL"))
    action = db.Column(db.String(60), nullable=False)
    details = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    actor = db.relationship("User", foreign_keys=[actor_id])

    def to_dict(self):
        return {
            "log_id": self.log_id,
            "actor_name": self.actor.name if self.actor else "System",
            "action": self.action,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
