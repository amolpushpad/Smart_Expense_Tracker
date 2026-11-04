import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from flask import Blueprint, current_app, jsonify, request, send_file, session
from sqlalchemy import false, func, or_, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename

from extensions import db
from models import (
    CORPORATE_ROLES,
    CorporateAuditLog,
    CorporateExpense,
    CorporateExpenseApproval,
    CorporateMembership,
    Department,
    Organization,
    User,
)
from services.corporate_receipt_service import MAX_RECEIPT_BYTES, receipt_file, save_receipt
from services.corporate_workflow_service import (
    CorporateWorkflowError,
    audit,
    export_expenses,
    filter_expenses,
    managed_department_ids,
    organization_payload,
    paginated_expenses,
    report_summary,
    role_dashboard,
    visible_expenses,
)
from services.auth_service import validate_email
corporate_workflow_bp = Blueprint("corporate_workflow", __name__)


@corporate_workflow_bp.errorhandler(CorporateWorkflowError)
def handle_workflow_error(error):
    return jsonify(
        success=False,
        message=str(error),
        **({"errors": error.errors} if error.errors else {}),
    ), error.status_code


def _membership():
    user_id = session.get("user_id")
    if not user_id or session.get("workspace_mode") != "corporate":
        return None
    return CorporateMembership.query.filter_by(
        user_id=user_id,
        membership_status="active",
    ).first()


def _require_membership():
    membership = _membership()
    if not membership:
        raise CorporateWorkflowError("Corporate authentication is required.", 401)
    if membership.organization.status != "active":
        raise CorporateWorkflowError("This organization is inactive.", 403)
    return membership


def _require_roles(membership, *roles):
    if membership.role not in roles:
        raise CorporateWorkflowError("Your corporate role does not permit this action.", 403)


def _body():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _check_upload_size():
    if request.content_length is not None and request.content_length > MAX_RECEIPT_BYTES + 65536:
        raise CorporateWorkflowError("Upload must be 5 MB or smaller.", 413)


def _organization_member(membership, membership_id):
    return CorporateMembership.query.filter_by(
        membership_id=membership_id,
        organization_id=membership.organization_id,
    ).first()


def _department_in_org(membership, department_id):
    if department_id in (None, ""):
        return None
    if isinstance(department_id, bool) or not str(department_id).isdigit():
        raise CorporateWorkflowError("Choose a valid department.")
    department = Department.query.filter_by(
        department_id=int(department_id),
        organization_id=membership.organization_id,
    ).first()
    if not department:
        raise CorporateWorkflowError("Choose a department in this organization.")
    return department


def _organization_expense(membership, expense_id):
    expense = visible_expenses(membership).filter_by(expense_id=expense_id).first()
    if not expense:
        raise CorporateWorkflowError("Corporate expense not found.", 404)
    return expense


def _expense_values(payload, partial=False):
    fields = {"amount", "date", "expense_date", "category", "merchant", "title", "description"}
    unknown = set(payload) - fields
    if unknown:
        raise CorporateWorkflowError("The expense contains unsupported fields.", errors={
            field: "This field is not supported." for field in sorted(unknown)
        })

    values = {}
    errors = {}
    if not partial or "amount" in payload:
        raw_amount = payload.get("amount")
        try:
            if isinstance(raw_amount, bool):
                raise InvalidOperation
            amount = Decimal(str(raw_amount))
            if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99") or amount.quantize(Decimal("0.01")) != amount:
                raise InvalidOperation
            values["amount"] = amount.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            errors["amount"] = "Amount must be positive with at most two decimal places."

    date_key = "expense_date" if "expense_date" in payload else "date"
    if not partial or date_key in payload:
        raw_date = payload.get(date_key)
        try:
            from services.expense_service import DATE_PATTERN
            from datetime import date

            if not isinstance(raw_date, str) or not DATE_PATTERN.fullmatch(raw_date):
                raise ValueError
            values["expense_date"] = date.fromisoformat(raw_date)
        except ValueError:
            errors["date"] = "Enter a valid date in YYYY-MM-DD format."

    if not partial or "category" in payload:
        category = payload.get("category")
        if not isinstance(category, str) or not category.strip() or len(category.strip()) > 80:
            errors["category"] = "Category must be between 1 and 80 characters."
        else:
            values["category"] = category.strip()

    merchant_key = "merchant" if "merchant" in payload else "title"
    if not partial or merchant_key in payload:
        merchant = payload.get(merchant_key)
        if not isinstance(merchant, str) or not merchant.strip() or len(merchant.strip()) > 160:
            errors["merchant"] = "Merchant must be between 1 and 160 characters."
        else:
            values["merchant"] = merchant.strip()

    if not partial or "description" in payload:
        description = payload.get("description")
        if description in (None, ""):
            values["description"] = None
        elif not isinstance(description, str) or len(description.strip()) > 500:
            errors["description"] = "Description must be at most 500 characters."
        else:
            values["description"] = description.strip() or None

    if errors:
        raise CorporateWorkflowError("Please correct the expense fields.", errors=errors)
    return values


def _audit_membership_change(membership, action, details):
    audit(membership.organization_id, session.get("user_id"), action, details)


@corporate_workflow_bp.get("/organization")
def get_organization():
    membership = _require_membership()
    return jsonify(success=True, data={
        "organization": organization_payload(membership.organization, include_code=membership.role == "Admin"),
        "membership": membership.to_dict(),
    })


@corporate_workflow_bp.put("/organization")
def update_organization():
    membership = _require_membership()
    _require_roles(membership, "Admin")
    payload = _body()
    allowed = {"name", "organization_name", "organization_email", "contact_phone", "address", "joining_enabled"}
    if set(payload) - allowed:
        raise CorporateWorkflowError("The organization contains unsupported fields.")

    organization = membership.organization
    name = payload.get("organization_name", payload.get("name", organization.name))
    email = payload.get("organization_email", organization.organization_email)
    phone = payload.get("contact_phone", organization.contact_phone)
    address = payload.get("address", organization.address)
    enabled = payload.get("joining_enabled", organization.joining_enabled)
    errors = {}
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 160:
        errors["name"] = "Organization name must be between 1 and 160 characters."
    elif name.strip() != organization.name and Organization.query.filter(
        func.lower(Organization.name) == name.strip().lower(),
        Organization.organization_id != organization.organization_id,
    ).first():
        errors["name"] = "An organization with this name already exists."
    if email not in (None, "") and (
        not isinstance(email, str) or len(email) > 254 or not validate_email(email.strip())
    ):
        errors["organization_email"] = "Enter a valid organization email address."
    if phone not in (None, "") and (
        not isinstance(phone, str) or len(phone.strip()) > 30
    ):
        errors["contact_phone"] = "Contact phone must be at most 30 characters."
    if address not in (None, "") and (
        not isinstance(address, str) or len(address.strip()) > 300
    ):
        errors["address"] = "Address must be at most 300 characters."
    if not isinstance(enabled, bool):
        errors["joining_enabled"] = "Joining enabled must be a boolean value."
    if errors:
        raise CorporateWorkflowError("Please correct the organization settings.", errors=errors)

    organization.name = name.strip()
    organization.organization_email = email.strip().lower() if isinstance(email, str) and email.strip() else None
    organization.contact_phone = phone.strip() if isinstance(phone, str) and phone.strip() else None
    organization.address = address.strip() if isinstance(address, str) and address.strip() else None
    organization.joining_enabled = enabled
    _audit_membership_change(membership, "organization_updated", "Organization settings updated.")
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise CorporateWorkflowError("An organization with this name already exists.", 409) from error
    return jsonify(success=True, message="Organization settings saved.", data={
        "organization": organization_payload(organization, include_code=True),
    })


@corporate_workflow_bp.post("/organization/regenerate-code")
def regenerate_joining_code():
    membership = _require_membership()
    _require_roles(membership, "Admin")
    organization = membership.organization
    for _ in range(10):
        code = secrets.token_urlsafe(9).upper()
        if not Organization.query.filter_by(joining_code=code).first():
            organization.joining_code = code
            break
    else:
        raise CorporateWorkflowError("Could not generate a unique joining code. Try again.", 503)
    _audit_membership_change(membership, "joining_code_regenerated", "Organization joining code was regenerated.")
    db.session.commit()
    return jsonify(success=True, message="A new joining code was generated.", data={
        "organization": organization_payload(organization, include_code=True),
    })


@corporate_workflow_bp.get("/members/search")
def list_members():
    membership = _require_membership()
    _require_roles(membership, "Admin")
    query = CorporateMembership.query.filter_by(organization_id=membership.organization_id).join(User)
    role = request.args.get("role")
    status = request.args.get("status")
    search = request.args.get("search", "").strip()
    if role:
        if role not in CORPORATE_ROLES:
            raise CorporateWorkflowError("Choose a valid role.")
        query = query.filter(CorporateMembership.role == role)
    if status:
        if status not in ("active", "inactive"):
            raise CorporateWorkflowError("Choose a valid membership status.")
        query = query.filter(CorporateMembership.membership_status == status)
    if len(search) > 100:
        raise CorporateWorkflowError("Search must be at most 100 characters.")
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    members = query.order_by(CorporateMembership.role, User.name).all()
    return jsonify(success=True, data={"members": [item.to_dict() for item in members]})


@corporate_workflow_bp.post("/members")
def add_member():
    membership = _require_membership()
    _require_roles(membership, "Admin")
    payload = _body()
    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")
    role = payload.get("role", "Employee")
    department = _department_in_org(membership, payload.get("department_id"))
    errors = {}
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        errors["name"] = "Name must be between 1 and 120 characters."
    if not isinstance(email, str) or len(email.strip()) > 254 or "@" not in email:
        errors["email"] = "Enter a valid email address."
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        errors["password"] = "Temporary password must be between 8 and 128 characters."
    if role not in CORPORATE_ROLES:
        errors["role"] = "Choose a valid corporate role."
    if errors:
        raise CorporateWorkflowError("Please correct the member fields.", errors=errors)
    normalized_email = email.strip().lower()
    if User.query.filter(func.lower(User.email) == normalized_email).first():
        raise CorporateWorkflowError("This email already has an account. Ask the user to join with the organization code.", 409)

    user = User(name=name.strip(), email=normalized_email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    new_membership = CorporateMembership(
        organization_id=membership.organization_id,
        user_id=user.user_id,
        department_id=department.department_id if department else None,
        role=role,
    )
    db.session.add(new_membership)
    _audit_membership_change(membership, "member_added", f"Added {user.email} as {role}.")
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise CorporateWorkflowError("The member could not be added.", 409) from error
    return jsonify(success=True, message="Member added.", data={"member": new_membership.to_dict()}), 201


@corporate_workflow_bp.put("/members/<int:membership_id>")
def update_member(membership_id):
    membership = _require_membership()
    _require_roles(membership, "Admin")
    target = _organization_member(membership, membership_id)
    if not target:
        raise CorporateWorkflowError("Team member not found.", 404)
    payload = _body()
    allowed = {"role", "department_id", "membership_status"}
    if set(payload) - allowed or not payload:
        raise CorporateWorkflowError("Provide supported member fields to update.")
    role = payload.get("role", target.role)
    status = payload.get("membership_status", target.membership_status)
    department = _department_in_org(membership, payload.get("department_id", target.department_id))
    if role not in CORPORATE_ROLES:
        raise CorporateWorkflowError("Choose a valid corporate role.")
    if status not in ("active", "inactive"):
        raise CorporateWorkflowError("Choose active or inactive membership status.")
    if target.membership_id == membership.membership_id and (role != "Admin" or status != "active"):
        raise CorporateWorkflowError("You cannot remove your own administrator access.")
    if target.role == "Admin" and (role != "Admin" or status != "active"):
        remaining = CorporateMembership.query.filter_by(
            organization_id=membership.organization_id,
            role="Admin",
            membership_status="active",
        ).count()
        if remaining <= 1:
            raise CorporateWorkflowError("An organization must keep at least one active administrator.")

    target.role = role
    target.membership_status = status
    target.department_id = department.department_id if department else None
    _audit_membership_change(membership, "member_updated", f"Updated membership {membership_id}.")
    db.session.commit()
    return jsonify(success=True, message="Member updated.", data={"member": target.to_dict()})


@corporate_workflow_bp.get("/departments")
def list_departments():
    membership = _require_membership()
    query = Department.query.filter_by(organization_id=membership.organization_id)
    if membership.role == "Employee":
        query = query.filter(Department.department_id == (membership.department_id or 0))
    elif membership.role == "Manager":
        query = query.filter(Department.department_id.in_(managed_department_ids(membership) or [0]))
    departments = query.order_by(Department.name).all()
    counts = dict(db.session.query(
        CorporateMembership.department_id,
        func.count(CorporateMembership.membership_id),
    ).filter(
        CorporateMembership.organization_id == membership.organization_id,
        CorporateMembership.membership_status == "active",
    ).group_by(CorporateMembership.department_id).all())
    return jsonify(success=True, data={"departments": [
        {
            **item.to_dict(),
            "department_name": item.name,
            "member_count": counts.get(item.department_id, 0),
        }
        for item in departments
    ]})


@corporate_workflow_bp.put("/departments/<int:department_id>")
def update_department(department_id):
    membership = _require_membership()
    _require_roles(membership, "Admin")
    department = Department.query.filter_by(
        department_id=department_id,
        organization_id=membership.organization_id,
    ).first()
    if not department:
        raise CorporateWorkflowError("Department not found.", 404)
    payload = _body()
    allowed = {"name", "department_name", "manager_id", "status"}
    if not payload or set(payload) - allowed:
        raise CorporateWorkflowError("Provide supported department fields to update.")
    name = payload.get("department_name", payload.get("name", department.name))
    status = payload.get("status", department.status)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise CorporateWorkflowError("Department name must be between 1 and 100 characters.")
    if status not in ("active", "inactive"):
        raise CorporateWorkflowError("Choose active or inactive department status.")
    manager_id = payload.get("manager_id", department.manager_id)
    manager = None
    if manager_id not in (None, ""):
        if isinstance(manager_id, bool) or not str(manager_id).isdigit():
            raise CorporateWorkflowError("Choose a valid department manager.")
        manager = CorporateMembership.query.filter_by(
            organization_id=membership.organization_id,
            user_id=int(manager_id),
            role="Manager",
            membership_status="active",
        ).first()
        if not manager:
            raise CorporateWorkflowError("The department manager must be an active manager in this organization.")
    department.name = name.strip()
    department.status = status
    department.manager_id = manager.user_id if manager else None
    if manager:
        manager.department_id = department.department_id
    _audit_membership_change(membership, "department_updated", f"Updated department {department.name}.")
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise CorporateWorkflowError("That department name already exists.", 409) from error
    return jsonify(success=True, message="Department updated.", data={"department": department.to_dict()})


@corporate_workflow_bp.get("/departments/<int:department_id>/members")
def department_members(department_id):
    membership = _require_membership()
    department = Department.query.filter_by(
        department_id=department_id,
        organization_id=membership.organization_id,
    ).first()
    if not department:
        raise CorporateWorkflowError("Department not found.", 404)
    if membership.role == "Manager" and department_id not in managed_department_ids(membership):
        raise CorporateWorkflowError("Department not found.", 404)
    if membership.role == "Employee":
        raise CorporateWorkflowError("Department not found.", 404)
    members = CorporateMembership.query.filter_by(
        organization_id=membership.organization_id,
        department_id=department_id,
        membership_status="active",
    ).order_by(CorporateMembership.role, CorporateMembership.membership_id).all()
    return jsonify(success=True, data={
        "department": department.to_dict(),
        "members": [item.to_dict() for item in members],
    })


@corporate_workflow_bp.get("/expenses/<int:expense_id>")
def get_expense(expense_id):
    membership = _require_membership()
    expense = _organization_expense(membership, expense_id)
    return jsonify(success=True, data={"expense": expense.to_dict(include_history=True)})


@corporate_workflow_bp.get("/expenses/search")
def search_expenses():
    membership = _require_membership()
    return jsonify(success=True, data=paginated_expenses(membership, request.args))


@corporate_workflow_bp.post("/expenses/with-receipt")
def submit_expense_with_receipt():
    membership = _require_membership()
    _require_roles(membership, "Employee", "Manager", "Admin")
    _check_upload_size()
    values, uploaded_path = _expense_values(request.form.to_dict()), None
    try:
        receipt = request.files.get("receipt")
        filename = None
        if receipt and receipt.filename:
            relative_path, filename, uploaded_path = save_receipt(receipt, membership.organization_id)
        else:
            relative_path = None
        expense = CorporateExpense(
            organization_id=membership.organization_id,
            submitter_id=membership.user_id,
            department_id=membership.department_id,
            amount=values["amount"],
            expense_date=values["expense_date"],
            category=values["category"],
            merchant=values["merchant"],
            description=values["description"],
            receipt_path=relative_path,
            receipt_filename=filename,
        )
        db.session.add(expense)
        audit(
            membership.organization_id,
            membership.user_id,
            "expense_submitted",
            f"Submitted corporate expense in {values['category']}.",
        )
        db.session.commit()
    except CorporateWorkflowError:
        db.session.rollback()
        if uploaded_path:
            uploaded_path.unlink(missing_ok=True)
        raise
    except SQLAlchemyError as error:
        db.session.rollback()
        if uploaded_path:
            uploaded_path.unlink(missing_ok=True)
        current_app.logger.exception("Corporate expense submission failed.")
        raise CorporateWorkflowError("The expense could not be saved. Please try again.", 500) from error
    return jsonify(
        success=True,
        message="Expense submitted for manager approval.",
        data={"expense": expense.to_dict()},
    ), 201


@corporate_workflow_bp.put("/expenses/<int:expense_id>")
def update_expense(expense_id):
    membership = _require_membership()
    _require_roles(membership, "Employee", "Admin")
    expense = _organization_expense(membership, expense_id)
    if expense.submitter_id != membership.user_id:
        raise CorporateWorkflowError("You can only edit your own expenses.", 403)
    if expense.status != "Pending Manager":
        raise CorporateWorkflowError("Only expenses awaiting manager review can be edited.", 409)
    payload = _body()
    values = _expense_values(payload, partial=True)
    for field, value in values.items():
        setattr(expense, field, value)
    expense.updated_at = datetime.now(timezone.utc)
    audit(membership.organization_id, membership.user_id, "expense_updated", f"Updated expense {expense.expense_id}.")
    db.session.commit()
    return jsonify(success=True, message="Expense updated.", data={"expense": expense.to_dict(include_history=True)})


@corporate_workflow_bp.post("/expenses/<int:expense_id>/receipt")
def replace_receipt(expense_id):
    membership = _require_membership()
    expense = _organization_expense(membership, expense_id)
    if expense.submitter_id != membership.user_id:
        raise CorporateWorkflowError("You can only add receipts to your own expenses.", 403)
    if expense.status != "Pending Manager":
        raise CorporateWorkflowError("Receipts can only be changed before manager review.", 409)
    _check_upload_size()
    receipt = request.files.get("receipt")
    if not receipt or not receipt.filename:
        raise CorporateWorkflowError("Choose a receipt file.")
    relative_path, filename, new_path = save_receipt(receipt, membership.organization_id)
    previous_path = receipt_file(expense.receipt_path)
    expense.receipt_path = relative_path
    expense.receipt_filename = filename
    try:
        audit(
            membership.organization_id,
            membership.user_id,
            "receipt_uploaded",
            f"Uploaded a receipt for expense {expense_id}.",
        )
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        new_path.unlink(missing_ok=True)
        current_app.logger.exception("Corporate receipt update failed.")
        raise CorporateWorkflowError("The receipt could not be saved. Please try again.", 500) from error
    if previous_path and previous_path != new_path:
        previous_path.unlink(missing_ok=True)
    return jsonify(success=True, message="Receipt uploaded.", data={"expense": expense.to_dict()})


@corporate_workflow_bp.get("/expenses/<int:expense_id>/receipt")
def download_receipt(expense_id):
    membership = _require_membership()
    expense = _organization_expense(membership, expense_id)
    path = receipt_file(expense.receipt_path)
    if not path:
        raise CorporateWorkflowError("Receipt not found.", 404)
    response = send_file(
        path,
        as_attachment=True,
        download_name=secure_filename(expense.receipt_filename or path.name),
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@corporate_workflow_bp.get("/approvals")
def approval_queue():
    membership = _require_membership()
    _require_roles(membership, "Manager", "Finance Officer", "Admin")
    queue_name = request.args.get("queue", "manager" if membership.role == "Manager" else "finance")
    if queue_name not in ("manager", "finance"):
        raise CorporateWorkflowError("Choose manager or finance approval queue.")
    status = "Pending Manager" if queue_name == "manager" else "Pending Finance"
    if membership.role == "Manager" and queue_name != "manager":
        raise CorporateWorkflowError("Managers can only review manager approvals.", 403)
    if membership.role == "Finance Officer" and queue_name != "finance":
        raise CorporateWorkflowError("Finance officers can only review finance approvals.", 403)
    query = CorporateExpense.query.filter_by(
        organization_id=membership.organization_id,
        status=status,
    )
    if membership.role == "Manager":
        department_ids = managed_department_ids(membership)
        query = query.filter(CorporateExpense.department_id.in_(department_ids)) if department_ids else query.filter(false())
    query = query.filter(CorporateExpense.submitter_id != membership.user_id)
    search = request.args.get("search", "").strip()
    if len(search) > 100:
        raise CorporateWorkflowError("Search must be at most 100 characters.")
    if search:
        pattern = f"%{search}%"
        query = query.join(User, User.user_id == CorporateExpense.submitter_id).filter(or_(
            CorporateExpense.merchant.ilike(pattern),
            User.name.ilike(pattern),
        ))
    expenses = query.order_by(CorporateExpense.expense_date, CorporateExpense.expense_id).limit(200).all()
    return jsonify(success=True, data={"expenses": [item.to_dict() for item in expenses]})


@corporate_workflow_bp.post("/approvals/<int:expense_id>/<action>")
def review_expense(expense_id, action):
    membership = _require_membership()
    if action not in ("approve", "reject", "pay"):
        raise CorporateWorkflowError("Choose approve, reject, or pay.")
    expense = CorporateExpense.query.filter_by(
        expense_id=expense_id,
        organization_id=membership.organization_id,
    ).with_for_update().first()
    if not expense:
        raise CorporateWorkflowError("Corporate expense not found.", 404)
    if expense.submitter_id == membership.user_id:
        raise CorporateWorkflowError("You cannot review your own expense.", 403)
    comments = _body().get("comments", "")
    if not isinstance(comments, str) or len(comments.strip()) > 500:
        raise CorporateWorkflowError("Comments must be at most 500 characters.")
    comments = comments.strip()

    previous_status = expense.status
    now = datetime.now(timezone.utc)
    if action == "pay":
        _require_roles(membership, "Finance Officer", "Admin")
        if previous_status != "Approved" or expense.paid_at is not None:
            raise CorporateWorkflowError("Only approved, unpaid expenses can be reimbursed.", 409)
        update_values = {"paid_at": now, "updated_at": now}
        history_status = "Paid"
        message = "Reimbursement marked as paid."
    else:
        if membership.role not in ("Manager", "Finance Officer", "Admin"):
            raise CorporateWorkflowError("Your corporate role does not permit expense review.", 403)
        if membership.role == "Manager":
            allowed_departments = managed_department_ids(membership)
            if previous_status != "Pending Manager" or expense.department_id not in allowed_departments:
                raise CorporateWorkflowError("This expense is not awaiting your department's review.", 403)
            update_values = {
                "status": "Pending Finance" if action == "approve" else "Rejected",
                "manager_id": membership.user_id,
                "manager_note": comments or None,
                "updated_at": now,
            }
        elif membership.role == "Finance Officer":
            if previous_status != "Pending Finance":
                raise CorporateWorkflowError("This expense is not awaiting finance review.", 409)
            update_values = {
                "status": "Approved" if action == "approve" else "Rejected",
                "finance_id": membership.user_id,
                "finance_note": comments or None,
                "updated_at": now,
            }
        else:
            if previous_status == "Pending Manager":
                update_values = {
                    "status": "Pending Finance" if action == "approve" else "Rejected",
                    "manager_id": membership.user_id,
                    "manager_note": comments or None,
                    "updated_at": now,
                }
            elif previous_status == "Pending Finance":
                update_values = {
                    "status": "Approved" if action == "approve" else "Rejected",
                    "finance_id": membership.user_id,
                    "finance_note": comments or None,
                    "updated_at": now,
                }
            else:
                raise CorporateWorkflowError("This expense is not awaiting review.", 409)
        if action == "reject" and len(comments) < 3:
            raise CorporateWorkflowError("A rejection reason of at least 3 characters is required.")
        if action == "reject":
            update_values["rejection_reason"] = comments
        history_status = update_values["status"]
        message = "Expense approved." if action == "approve" else "Expense rejected."

    update_query = update(CorporateExpense).where(
        CorporateExpense.expense_id == expense.expense_id,
        CorporateExpense.status == previous_status,
    )
    if action == "pay":
        update_query = update_query.where(CorporateExpense.paid_at.is_(None))
    result = db.session.execute(update_query.values(**update_values))
    if result.rowcount != 1:
        db.session.rollback()
        raise CorporateWorkflowError("This expense was updated by another reviewer. Refresh and try again.", 409)
    db.session.add(CorporateExpenseApproval(
        expense_id=expense.expense_id,
        reviewer_id=membership.user_id,
        previous_status=previous_status,
        new_status=history_status,
        comments=comments or None,
        action_date=now,
    ))
    audit(
        membership.organization_id,
        membership.user_id,
        f"expense_{action}",
        f"{action.capitalize()} expense {expense.expense_id}.",
    )
    db.session.commit()
    db.session.refresh(expense)
    result_data = expense.to_dict(include_history=True)
    result_data["reimbursement_status"] = "Paid" if expense.paid_at else (
        "Awaiting reimbursement" if expense.status == "Approved" else "Not approved"
    )
    return jsonify(success=True, message=message, data={"expense": result_data})


@corporate_workflow_bp.get("/reimbursements")
def reimbursements():
    membership = _require_membership()
    _require_roles(membership, "Employee", "Finance Officer", "Admin", "Executive")
    query = CorporateExpense.query.filter_by(
        organization_id=membership.organization_id,
        status="Approved",
    )
    if membership.role == "Employee":
        query = query.filter_by(submitter_id=membership.user_id)
    status = request.args.get("status")
    if status == "unpaid":
        query = query.filter(CorporateExpense.paid_at.is_(None))
    elif status == "paid":
        query = query.filter(CorporateExpense.paid_at.is_not(None))
    elif status:
        raise CorporateWorkflowError("Choose paid or unpaid reimbursement status.")
    rows = query.order_by(CorporateExpense.expense_date.desc()).limit(500).all()
    return jsonify(success=True, data={"reimbursements": [
        {
            **item.to_dict(),
            "reimbursement_status": "Paid" if item.paid_at else "Awaiting reimbursement",
        }
        for item in rows
    ]})


@corporate_workflow_bp.get("/dashboard/<role_name>")
def dashboard_for_role(role_name):
    membership = _require_membership()
    role_by_path = {
        "admin": "Admin",
        "employee": "Employee",
        "manager": "Manager",
        "finance": "Finance Officer",
        "executive": "Executive",
    }
    if role_name not in role_by_path:
        raise CorporateWorkflowError("Dashboard not found.", 404)
    if role_by_path[role_name] != membership.role:
        raise CorporateWorkflowError("Your corporate role does not permit this dashboard.", 403)
    data = role_dashboard(membership)
    return jsonify(success=True, data={
        **data,
        "organization": organization_payload(
            data["organization"],
            include_code=membership.role == "Admin",
        ),
        "department": data["department"].name if data["department"] else None,
    })


@corporate_workflow_bp.get("/reports/summary")
def corporate_report_summary():
    membership = _require_membership()
    _require_roles(membership, "Admin", "Manager", "Finance Officer", "Executive")
    return jsonify(success=True, data=report_summary(membership, request.args))


@corporate_workflow_bp.get("/reports/export")
def export_corporate_report():
    membership = _require_membership()
    _require_roles(membership, "Admin", "Manager", "Finance Officer", "Executive")
    response = send_file(
        BytesIO(export_expenses(membership, request.args).encode("utf-8")),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name="corporate-expenses.csv",
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


@corporate_workflow_bp.get("/reports/transactions")
def corporate_transactions():
    membership = _require_membership()
    _require_roles(membership, "Admin", "Manager", "Finance Officer", "Executive")
    query = filter_expenses(visible_expenses(membership), request.args, membership)
    rows = query.order_by(
        CorporateExpense.expense_date.desc(),
        CorporateExpense.expense_id.desc(),
    ).limit(50).all()
    return jsonify(success=True, data={"transactions": [item.to_dict() for item in rows]})


@corporate_workflow_bp.get("/audit-log")
def organization_audit_log():
    membership = _require_membership()
    _require_roles(membership, "Admin")
    rows = CorporateAuditLog.query.filter_by(
        organization_id=membership.organization_id,
    ).order_by(CorporateAuditLog.created_at.desc(), CorporateAuditLog.log_id.desc()).limit(100).all()
    return jsonify(success=True, data={"events": [item.to_dict() for item in rows]})


@corporate_workflow_bp.get("/profile")
def corporate_profile():
    membership = _require_membership()
    return jsonify(success=True, data={
        "user": membership.user.to_safe_dict(),
        "membership": membership.to_dict(),
        "organization": organization_payload(membership.organization),
    })
