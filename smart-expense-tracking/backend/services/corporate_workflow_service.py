import csv
import re
from datetime import date
from decimal import Decimal
from io import StringIO

from sqlalchemy import func, or_

from extensions import db
from models import (
    CorporateAuditLog,
    CorporateExpense,
    CorporateMembership,
    Department,
    User,
)

EXPENSE_STATUSES = ("Pending Manager", "Pending Finance", "Approved", "Rejected")
ROLES = ("Admin", "Employee", "Manager", "Finance Officer", "Executive")
MEMBERSHIP_STATUSES = ("active", "inactive")
DEPARTMENT_STATUSES = ("active", "inactive")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CorporateWorkflowError(ValueError):
    def __init__(self, message, status_code=400, errors=None):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or {}


def audit(organization_id, actor_id, action, details=None):
    db.session.add(CorporateAuditLog(
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        details=(details or "")[:500] or None,
    ))


def managed_department_ids(membership):
    query = Department.query.filter_by(
        organization_id=membership.organization_id,
        manager_id=membership.user_id,
        status="active",
    )
    department_ids = {department_id for (department_id,) in query.with_entities(Department.department_id).all()}
    if membership.department_id:
        department = Department.query.filter_by(
            department_id=membership.department_id,
            organization_id=membership.organization_id,
            status="active",
        ).first()
        if department:
            department_ids.add(department.department_id)
    return sorted(department_ids)


def visible_expenses(membership):
    query = CorporateExpense.query.filter_by(organization_id=membership.organization_id)
    if membership.role == "Employee":
        return query.filter_by(submitter_id=membership.user_id)
    if membership.role == "Manager":
        department_ids = managed_department_ids(membership)
        return query.filter(CorporateExpense.department_id.in_(department_ids)) if department_ids else query.filter(db.false())
    return query


def parse_date_filter(raw, field):
    try:
        if not isinstance(raw, str) or not DATE_PATTERN.fullmatch(raw):
            raise ValueError
        return date.fromisoformat(raw)
    except ValueError as error:
        raise CorporateWorkflowError(f"{field.replace('_', ' ').capitalize()} must use YYYY-MM-DD.") from error


def filter_expenses(query, args, membership):
    status = args.get("status")
    if status:
        statuses = [value for value in status.split(",") if value]
        if any(value not in EXPENSE_STATUSES for value in statuses):
            raise CorporateWorkflowError("Choose a valid expense status.")
        query = query.filter(CorporateExpense.status.in_(statuses))

    for parameter, column in (
        ("department_id", CorporateExpense.department_id),
        ("user_id", CorporateExpense.submitter_id),
    ):
        raw = args.get(parameter)
        if raw:
            if not raw.isdigit() or int(raw) < 1:
                raise CorporateWorkflowError(f"{parameter.replace('_', ' ').capitalize()} must be a positive number.")
            if membership.role in ("Employee", "Manager"):
                allowed = {membership.department_id} if parameter == "department_id" and membership.department_id else set()
                if parameter == "department_id" and membership.role == "Manager":
                    allowed = set(managed_department_ids(membership))
                if parameter == "user_id":
                    if membership.role == "Employee":
                        allowed = {membership.user_id}
                    else:
                        department_ids = managed_department_ids(membership)
                        allowed = {
                            user_id for (user_id,) in CorporateMembership.query.with_entities(
                                CorporateMembership.user_id
                            ).filter(
                                CorporateMembership.organization_id == membership.organization_id,
                                CorporateMembership.department_id.in_(department_ids or [0]),
                                CorporateMembership.membership_status == "active",
                            ).all()
                        }
                if int(raw) not in allowed:
                    raise CorporateWorkflowError("The selected filter is outside your access scope.", 403)
            query = query.filter(column == int(raw))

    category = args.get("category", "").strip()
    if category:
        if len(category) > 80:
            raise CorporateWorkflowError("Category filter is too long.")
        query = query.filter(CorporateExpense.category == category)

    for parameter, operator in (("start_date", ">="), ("end_date", "<=")):
        raw = args.get(parameter)
        if raw:
            value = parse_date_filter(raw, parameter)
            query = query.filter(
                CorporateExpense.expense_date >= value
                if operator == ">="
                else CorporateExpense.expense_date <= value
            )
    if args.get("start_date") and args.get("end_date"):
        start_date = parse_date_filter(args["start_date"], "start_date")
        end_date = parse_date_filter(args["end_date"], "end_date")
        if start_date > end_date:
            raise CorporateWorkflowError("Start date must be on or before end date.")

    search = args.get("search", "").strip()
    if len(search) > 100:
        raise CorporateWorkflowError("Search must be at most 100 characters.")
    if search:
        pattern = f"%{search}%"
        query = query.join(User, User.user_id == CorporateExpense.submitter_id).filter(or_(
            CorporateExpense.merchant.ilike(pattern),
            CorporateExpense.description.ilike(pattern),
            CorporateExpense.category.ilike(pattern),
            User.name.ilike(pattern),
        ))
    return query


def paginated_expenses(membership, args):
    query = filter_expenses(visible_expenses(membership), args, membership)
    page_raw = args.get("page", "1")
    per_page_raw = args.get("per_page", "20")
    if not page_raw.isdigit() or int(page_raw) < 1:
        raise CorporateWorkflowError("Page must be a positive number.")
    if not per_page_raw.isdigit() or not 1 <= int(per_page_raw) <= 100:
        raise CorporateWorkflowError("Page size must be between 1 and 100.")
    pagination = query.order_by(
        CorporateExpense.expense_date.desc(),
        CorporateExpense.expense_id.desc(),
    ).paginate(page=int(page_raw), per_page=int(per_page_raw), error_out=False)
    return {
        "expenses": [row.to_dict(include_history=True) for row in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def _status_metrics(query):
    grouped = query.with_entities(
        CorporateExpense.status,
        func.count(CorporateExpense.expense_id),
        func.coalesce(func.sum(CorporateExpense.amount), 0),
    ).group_by(CorporateExpense.status).all()
    values = {status: {"count": 0, "amount": Decimal("0.00")} for status in EXPENSE_STATUSES}
    for status, count, amount in grouped:
        values[status] = {"count": count, "amount": Decimal(amount)}
    paid = query.filter(CorporateExpense.status == "Approved", CorporateExpense.paid_at.is_not(None))
    values["Paid"] = {
        "count": paid.count(),
        "amount": Decimal(paid.with_entities(func.coalesce(func.sum(CorporateExpense.amount), 0)).scalar() or 0),
    }
    awaiting_payment = query.filter(CorporateExpense.status == "Approved", CorporateExpense.paid_at.is_(None))
    values["Approved"] = {
        "count": awaiting_payment.count(),
        "amount": Decimal(
            awaiting_payment.with_entities(func.coalesce(func.sum(CorporateExpense.amount), 0)).scalar() or 0
        ),
    }
    return values


def report_summary(membership, args):
    query = filter_expenses(visible_expenses(membership), args, membership)
    query = query.order_by(None)
    metrics = _status_metrics(query)
    department_rows = query.join(
        Department, Department.department_id == CorporateExpense.department_id, isouter=True
    ).with_entities(
        Department.name,
        func.count(CorporateExpense.expense_id),
        func.coalesce(func.sum(CorporateExpense.amount), 0),
    ).group_by(Department.name).order_by(Department.name).all()
    category_rows = query.with_entities(
        CorporateExpense.category,
        func.count(CorporateExpense.expense_id),
        func.coalesce(func.sum(CorporateExpense.amount), 0),
    ).group_by(CorporateExpense.category).order_by(CorporateExpense.category).all()

    result = {
        "summary": {
            "submitted_count": sum(item["count"] for item in metrics.values()),
            "submitted_amount": format(sum((item["amount"] for item in metrics.values()), Decimal("0.00")), ".2f"),
            "pending_manager_count": metrics["Pending Manager"]["count"],
            "pending_manager_amount": format(metrics["Pending Manager"]["amount"], ".2f"),
            "pending_finance_count": metrics["Pending Finance"]["count"],
            "pending_finance_amount": format(metrics["Pending Finance"]["amount"], ".2f"),
            "approved_count": metrics["Approved"]["count"],
            "approved_amount": format(metrics["Approved"]["amount"], ".2f"),
            "paid_count": metrics["Paid"]["count"],
            "paid_amount": format(metrics["Paid"]["amount"], ".2f"),
            "rejected_count": metrics["Rejected"]["count"],
            "rejected_amount": format(metrics["Rejected"]["amount"], ".2f"),
        },
        "by_department": [
            {"department_name": name or "Unassigned", "submitted_count": count, "submitted_amount": format(Decimal(amount), ".2f")}
            for name, count, amount in department_rows
        ],
        "by_category": [
            {"category": category, "submitted_count": count, "submitted_amount": format(Decimal(amount), ".2f")}
            for category, count, amount in category_rows
        ],
    }
    if membership.role in ("Admin", "Finance Officer", "Executive"):
        employee_rows = query.join(User, User.user_id == CorporateExpense.submitter_id).with_entities(
            User.name,
            func.count(CorporateExpense.expense_id),
            func.coalesce(func.sum(CorporateExpense.amount), 0),
        ).group_by(User.name).order_by(User.name).all()
        result["by_employee"] = [
            {"employee_name": name, "submitted_count": count, "submitted_amount": format(Decimal(amount), ".2f")}
            for name, count, amount in employee_rows
        ]

    dialect = db.engine.dialect.name
    month_expression = (
        func.date_format(CorporateExpense.expense_date, "%Y-%m")
        if dialect == "mysql"
        else func.strftime("%Y-%m", CorporateExpense.expense_date)
    )
    monthly_rows = query.with_entities(
        month_expression,
        func.count(CorporateExpense.expense_id),
        func.coalesce(func.sum(CorporateExpense.amount), 0),
    ).group_by(month_expression).order_by(month_expression).all()
    result["monthly"] = [
        {"month": month, "submitted_count": count, "submitted_amount": format(Decimal(amount), ".2f")}
        for month, count, amount in monthly_rows
    ]
    return result


def csv_safe(value):
    text = str(value or "")
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def export_expenses(membership, args):
    query = filter_expenses(visible_expenses(membership), args, membership).order_by(
        CorporateExpense.expense_date.desc(),
        CorporateExpense.expense_id.desc(),
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "amount", "category", "merchant", "description", "status", "submitter", "department", "paid"])
    for expense in query.limit(10000).all():
        writer.writerow([
            expense.expense_date.isoformat(),
            format(expense.amount, ".2f"),
            csv_safe(expense.category),
            csv_safe(expense.merchant),
            csv_safe(expense.description),
            expense.status,
            csv_safe(expense.submitter.name),
            csv_safe(expense.department.name if expense.department else ""),
            "yes" if expense.paid_at else "no",
        ])
    return "\ufeff" + output.getvalue()


def role_dashboard(membership):
    query = visible_expenses(membership)
    metrics = _status_metrics(query)
    total_amount = sum((item["amount"] for item in metrics.values()), Decimal("0.00"))
    recent = query.order_by(
        CorporateExpense.expense_date.desc(),
        CorporateExpense.expense_id.desc(),
    ).limit(10).all()
    return {
        "organization": membership.organization,
        "role": membership.role,
        "department": membership.department,
        "summary": {
            "expense_count": sum(item["count"] for item in metrics.values()),
            "total_amount": format(total_amount, ".2f"),
            "pending_manager": metrics["Pending Manager"]["count"],
            "pending_finance": metrics["Pending Finance"]["count"],
            "approved": metrics["Approved"]["count"],
            "paid": metrics["Paid"]["count"],
            "rejected": metrics["Rejected"]["count"],
        },
        "recent_expenses": [expense.to_dict() for expense in recent],
    }


def organization_payload(organization, include_code=False):
    result = {
        "organization_id": organization.organization_id,
        "name": organization.name,
        "organization_name": organization.name,
        "organization_email": organization.organization_email,
        "contact_phone": organization.contact_phone,
        "address": organization.address,
        "status": organization.status,
        "joining_enabled": bool(organization.joining_enabled),
        "created_at": organization.created_at.isoformat() if organization.created_at else None,
    }
    if include_code:
        result["joining_code"] = organization.joining_code
        result["organization_code"] = organization.joining_code
    return result
