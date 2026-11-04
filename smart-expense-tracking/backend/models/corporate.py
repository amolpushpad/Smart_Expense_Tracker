import secrets
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, Numeric

from extensions import db


CORPORATE_ROLES = ("Admin", "Employee", "Manager", "Finance Officer", "Executive")


class Organization(db.Model):
    __tablename__ = "corporate_organizations"

    organization_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, unique=True)
    joining_code = db.Column(db.String(24), nullable=False, unique=True, default=lambda: secrets.token_urlsafe(9).upper())
    organization_email = db.Column(db.String(254))
    contact_phone = db.Column(db.String(30))
    address = db.Column(db.String(300))
    status = db.Column(db.String(20), nullable=False, default="active")
    joining_enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    departments = db.relationship("Department", back_populates="organization", cascade="all, delete-orphan")
    memberships = db.relationship("CorporateMembership", back_populates="organization", cascade="all, delete-orphan")


class Department(db.Model):
    __tablename__ = "corporate_departments"
    __table_args__ = (db.UniqueConstraint("organization_id", "name", name="uq_corporate_department_name"),)

    department_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("corporate_organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="SET NULL"), index=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    organization = db.relationship("Organization", back_populates="departments")
    manager = db.relationship("User", foreign_keys=[manager_id])

    def to_dict(self):
        return {
            "department_id": self.department_id,
            "organization_id": self.organization_id,
            "name": self.name,
            "manager_id": self.manager_id,
            "manager_name": self.manager.name if self.manager else None,
            "status": self.status,
        }


class CorporateMembership(db.Model):
    __tablename__ = "corporate_memberships"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "user_id", name="uq_corporate_membership_user"),
        CheckConstraint(
            "role IN ('Admin', 'Employee', 'Manager', 'Finance Officer', 'Executive')",
            name="ck_corporate_membership_role",
        ),
    )

    membership_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("corporate_organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("corporate_departments.department_id", ondelete="SET NULL"), index=True)
    role = db.Column(db.String(30), nullable=False, default="Employee")
    membership_status = db.Column(db.String(20), nullable=False, default="active")
    joined_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    organization = db.relationship("Organization", back_populates="memberships")
    user = db.relationship("User")
    department = db.relationship("Department")

    def to_dict(self):
        return {
            "membership_id": self.membership_id,
            "user_id": self.user_id,
            "name": self.user.name,
            "email": self.user.email,
            "role": self.role,
            "department_id": self.department_id,
            "department": self.department.name if self.department else None,
            "membership_status": self.membership_status,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
        }


class CorporateExpense(db.Model):
    __tablename__ = "corporate_expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_corporate_expense_positive_amount"),
        CheckConstraint(
            "status IN ('Pending Manager', 'Pending Finance', 'Approved', 'Rejected')",
            name="ck_corporate_expense_status",
        ),
        Index("ix_corporate_expense_org_date", "organization_id", "expense_date"),
        Index("ix_corporate_expense_org_status", "organization_id", "status"),
    )

    expense_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("corporate_organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("corporate_departments.department_id", ondelete="SET NULL"), index=True)
    amount = db.Column(Numeric(12, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False, index=True)
    category = db.Column(db.String(80), nullable=False)
    merchant = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(500))
    status = db.Column(db.String(24), nullable=False, default="Pending Manager", index=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="SET NULL"))
    manager_note = db.Column(db.String(500))
    finance_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="SET NULL"))
    finance_note = db.Column(db.String(500))
    rejection_reason = db.Column(db.String(500))
    receipt_path = db.Column(db.String(255))
    receipt_filename = db.Column(db.String(255))
    paid_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    submitter = db.relationship("User", foreign_keys=[submitter_id])
    department = db.relationship("Department")
    manager = db.relationship("User", foreign_keys=[manager_id])
    finance_officer = db.relationship("User", foreign_keys=[finance_id])
    approvals = db.relationship(
        "CorporateExpenseApproval",
        back_populates="expense",
        cascade="all, delete-orphan",
        order_by="CorporateExpenseApproval.approval_id",
    )

    def to_dict(self, include_history=False):
        result = {
            "expense_id": self.expense_id,
            "amount": format(self.amount, ".2f"),
            "date": self.expense_date.isoformat(),
            "expense_date": self.expense_date.isoformat(),
            "category": self.category,
            "merchant": self.merchant,
            "title": self.merchant,
            "description": self.description,
            "status": self.status,
            "approval_status": self.status,
            "submitter": self.submitter.name,
            "submitter_id": self.submitter_id,
            "department": self.department.name if self.department else None,
            "department_id": self.department_id,
            "manager_note": self.manager_note,
            "finance_note": self.finance_note,
            "rejection_reason": self.rejection_reason,
            "has_receipt": bool(self.receipt_path),
            "receipt_filename": self.receipt_filename,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_history:
            result["history"] = [approval.to_dict() for approval in self.approvals]
        return result
