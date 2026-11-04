from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (
    CORPORATE_ROLES,
    CorporateExpense,
    CorporateMembership,
    Department,
    Organization,
    User,
)
from services.corporate_workflow_service import managed_department_ids, visible_expenses
from services.auth_service import validate_email

corporate_bp = Blueprint("corporate", __name__)
EXPENSE_STATUSES = ("Pending Manager", "Pending Finance", "Approved", "Rejected")


def _body():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _membership():
    user_id = session.get("user_id")
    if not user_id or session.get("workspace_mode") != "corporate":
        return None
    membership = CorporateMembership.query.filter_by(
        user_id=user_id,
        membership_status="active",
    ).first()
    return membership if membership and membership.organization.status == "active" else None


def _error(message, status=400):
    return jsonify(success=False, message=message), status


def _membership_response(membership, include_code=True):
    organization = {
        "organization_id": membership.organization.organization_id,
        "name": membership.organization.name,
    }
    if include_code:
        organization["joining_code"] = membership.organization.joining_code
    return {
        "workspace_mode": "corporate",
        "role": membership.role,
        "organization": organization,
        "department": membership.department.name if membership.department else None,
    }


def _create_user(name, email, password):
    name = name.strip() if isinstance(name, str) else ""
    email = email.strip().lower() if isinstance(email, str) else ""
    if not name or len(name) > 120:
        return None, "Name must be between 1 and 120 characters."
    if not validate_email(email):
        return None, "Enter a valid email address."
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return None, "Password must be between 8 and 128 characters."
    if User.query.filter_by(email=email).first():
        return None, "An account with this email already exists."
    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return None, "An account with this email already exists."
    return user, None


@corporate_bp.post("/organizations")
def create_organization():
    payload = _body()
    name = payload.get("organization_name")
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > 160:
        return _error("Organization name must be between 1 and 160 characters.")
    if Organization.query.filter_by(name=name).first():
        return _error("An organization with this name already exists.", 409)

    user, error = _create_user(payload.get("name"), payload.get("email"), payload.get("password"))
    if error:
        return _error(error, 409 if "already exists" in error else 400)
    organization = Organization(name=name)
    db.session.add(organization)
    db.session.flush()
    department = Department(organization_id=organization.organization_id, name="General")
    db.session.add(department)
    db.session.flush()
    membership = CorporateMembership(
        organization_id=organization.organization_id,
        user_id=user.user_id,
        department_id=department.department_id,
        role="Admin",
    )
    db.session.add(membership)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("Could not create the organization. Check that the name and email are unique.", 409)
    return jsonify(
        success=True,
        message="Organization created. Sign in using Corporate Mode.",
        data={"organization": _membership_response(membership)["organization"], "role": membership.role},
    ), 201


@corporate_bp.post("/join")
def join_organization():
    payload = _body()
    code = payload.get("joining_code")
    code = code.strip().upper() if isinstance(code, str) else ""
    organization = Organization.query.filter_by(joining_code=code).first()
    if not organization:
        return _error("That organization joining code was not found.", 404)
    if organization.status != "active" or not organization.joining_enabled:
        return _error("This organization is not accepting new members.", 403)
    user, error = _create_user(payload.get("name"), payload.get("email"), payload.get("password"))
    if error:
        return _error(error, 409 if "already exists" in error else 400)
    department = Department.query.filter_by(
        organization_id=organization.organization_id,
        name="General",
        status="active",
    ).first()
    membership = CorporateMembership(
        organization_id=organization.organization_id,
        user_id=user.user_id,
        department_id=department.department_id if department else None,
        role="Employee",
    )
    db.session.add(membership)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("Could not join this organization with the provided account.", 409)
    return jsonify(success=True, message="Account created. Sign in using Corporate Mode.", data={"organization": organization.name}), 201


@corporate_bp.get("/overview")
def overview():
    membership = _membership()
    if not membership:
        return _error("Corporate authentication is required.", 401)

    query = visible_expenses(membership)
    expenses = query.order_by(CorporateExpense.expense_date.desc(), CorporateExpense.expense_id.desc()).limit(100).all()

    totals_query = visible_expenses(membership)
    counts = {status: 0 for status in EXPENSE_STATUSES}
    amount = Decimal("0.00")
    for row in totals_query.all():
        counts[row.status] += 1
        amount += row.amount

    departments = Department.query.filter_by(organization_id=membership.organization_id).order_by(Department.name).all()
    pending = []
    if membership.role in ("Manager", "Admin"):
        manager_queue = CorporateExpense.query.filter_by(
            organization_id=membership.organization_id, status="Pending Manager"
        )
        if membership.role == "Manager":
            manager_queue = manager_queue.filter(
                CorporateExpense.department_id.in_(managed_department_ids(membership) or [0])
            )
        pending.extend(manager_queue.order_by(CorporateExpense.expense_date.desc()).all())
    if membership.role in ("Finance Officer", "Admin"):
        pending.extend(CorporateExpense.query.filter_by(
            organization_id=membership.organization_id, status="Pending Finance"
        ).order_by(CorporateExpense.expense_date.desc()).all())

    data = {
        "organization": _membership_response(
            membership,
            include_code=membership.role == "Admin",
        )["organization"],
        "role": membership.role,
        "department": membership.department.name if membership.department else None,
        "summary": {
            "expense_count": sum(counts.values()),
            "total_amount": format(amount, ".2f"),
            "pending_manager": counts["Pending Manager"],
            "pending_finance": counts["Pending Finance"],
            "approved": counts["Approved"],
            "rejected": counts["Rejected"],
        },
        "departments": [
            {"department_id": item.department_id, "name": item.name} for item in departments
        ],
        "expenses": [item.to_dict() for item in expenses],
        "approvals": [item.to_dict() for item in pending],
    }
    if membership.role == "Admin":
        data["members"] = [
            item.to_dict()
            for item in CorporateMembership.query.filter_by(organization_id=membership.organization_id)
            .order_by(CorporateMembership.role, CorporateMembership.membership_id).all()
        ]
    return jsonify(success=True, data=data)


@corporate_bp.post("/departments")
def create_department():
    membership = _membership()
    if not membership:
        return _error("Corporate authentication is required.", 401)
    if membership.role != "Admin":
        return _error("Only organization admins can manage departments.", 403)
    name = _body().get("name")
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > 100:
        return _error("Department name must be between 1 and 100 characters.")
    department = Department(organization_id=membership.organization_id, name=name)
    db.session.add(department)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("That department already exists.", 409)
    return jsonify(success=True, data={"department_id": department.department_id, "name": department.name}), 201


@corporate_bp.patch("/members/<int:membership_id>")
def update_member(membership_id):
    membership = _membership()
    if not membership:
        return _error("Corporate authentication is required.", 401)
    if membership.role != "Admin":
        return _error("Only organization admins can manage team members.", 403)
    target = CorporateMembership.query.filter_by(
        membership_id=membership_id, organization_id=membership.organization_id
    ).first()
    if not target:
        return _error("Team member not found.", 404)
    payload = _body()
    role = payload.get("role", target.role)
    if role not in CORPORATE_ROLES:
        return _error("Choose a valid corporate role.")
    if target.membership_id == membership.membership_id and role != "Admin":
        return _error("You cannot remove your own admin role.")
    department_id = payload.get("department_id", target.department_id)
    if department_id is not None:
        department = Department.query.filter_by(
            department_id=department_id, organization_id=membership.organization_id
        ).first()
        if not department:
            return _error("Choose a department in this organization.")
    target.role = role
    target.department_id = department_id
    db.session.commit()
    return jsonify(success=True, data={"member": target.to_dict()})


@corporate_bp.get("/expenses")
def list_expenses():
    membership = _membership()
    if not membership:
        return _error("Corporate authentication is required.", 401)
    query = visible_expenses(membership)
    status = request.args.get("status")
    if status:
        if status not in EXPENSE_STATUSES:
            return _error("Choose a valid expense status.")
        query = query.filter_by(status=status)
    rows = query.order_by(CorporateExpense.expense_date.desc(), CorporateExpense.expense_id.desc()).limit(200).all()
    return jsonify(success=True, data={"expenses": [row.to_dict() for row in rows]})


@corporate_bp.post("/expenses")
def submit_expense():
    membership = _membership()
    if not membership:
        return _error("Corporate authentication is required.", 401)
    payload = _body()
    try:
        amount = Decimal(str(payload.get("amount", "")))
    except (InvalidOperation, ValueError):
        return _error("Enter a valid expense amount.")
    if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
        return _error("Expense amount must be greater than zero and within the supported limit.")
    try:
        expense_date = date.fromisoformat(payload.get("date", ""))
    except (TypeError, ValueError):
        return _error("Enter a valid expense date.")
    category = payload.get("category")
    merchant = payload.get("merchant")
    description = payload.get("description", "")
    if not isinstance(category, str) or not category.strip() or len(category.strip()) > 80:
        return _error("Category is required and must be 80 characters or fewer.")
    if not isinstance(merchant, str) or not merchant.strip() or len(merchant.strip()) > 160:
        return _error("Merchant is required and must be 160 characters or fewer.")
    if not isinstance(description, str) or len(description) > 500:
        return _error("Description must be 500 characters or fewer.")
    try:
        stored_amount = amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        return _error("Enter an expense amount with no more than two decimal places.")
    if stored_amount <= 0:
        return _error("Expense amount must be at least one cent.")
    expense = CorporateExpense(
        organization_id=membership.organization_id,
        submitter_id=membership.user_id,
        department_id=membership.department_id,
        amount=stored_amount,
        expense_date=expense_date,
        category=category.strip(),
        merchant=merchant.strip(),
        description=description.strip() or None,
        status="Pending Manager",
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify(success=True, message="Expense submitted for manager approval.", data={"expense": expense.to_dict()}), 201


@corporate_bp.post("/expenses/<int:expense_id>/decision")
def decide_expense(expense_id):
    membership = _membership()
    if not membership:
        return _error("Corporate authentication is required.", 401)
    expense = CorporateExpense.query.filter_by(
        expense_id=expense_id, organization_id=membership.organization_id
    ).first()
    if not expense:
        return _error("Corporate expense not found.", 404)
    payload = _body()
    approve = payload.get("approve")
    note = payload.get("note", "")
    if not isinstance(approve, bool):
        return _error("An approval decision is required.")
    if not isinstance(note, str) or len(note) > 500:
        return _error("Approval notes must be 500 characters or fewer.")
    if expense.submitter_id == membership.user_id:
        return _error("You cannot approve your own expense.", 403)

    if expense.status == "Pending Manager" and membership.role in ("Manager", "Admin"):
        if membership.role == "Manager" and expense.department_id not in managed_department_ids(membership):
            return _error("This expense is outside your department.", 403)
        expense.manager_id = membership.user_id
        expense.manager_note = note.strip() or None
        expense.status = "Pending Finance" if approve else "Rejected"
    elif expense.status == "Pending Finance" and membership.role in ("Finance Officer", "Admin"):
        expense.finance_id = membership.user_id
        expense.finance_note = note.strip() or None
        expense.status = "Approved" if approve else "Rejected"
    else:
        return _error("Your role cannot decide this expense at its current approval stage.", 403)
    db.session.commit()
    return jsonify(success=True, message=f"Expense {expense.status.lower()}.", data={"expense": expense.to_dict()})


@corporate_bp.get("/members")
def list_members():
    membership = _membership()
    if not membership:
        return _error("Corporate authentication is required.", 401)
    if membership.role != "Admin":
        return _error("Only organization admins can view team administration.", 403)
    members = CorporateMembership.query.filter_by(organization_id=membership.organization_id).order_by(
        CorporateMembership.role, CorporateMembership.membership_id
    ).all()
    return jsonify(success=True, data={"members": [item.to_dict() for item in members]})
