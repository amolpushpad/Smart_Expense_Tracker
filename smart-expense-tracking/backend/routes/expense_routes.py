from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Expense, User
from services.expense_service import expense_list_response, expense_query_for_user, validate_expense_payload

expense_bp = Blueprint("expenses", __name__)


def _user_id():
    user_id = session.get("user_id")
    return user_id if user_id and db.session.get(User, user_id) else None


def _expense_or_404(expense_id, user_id):
    return Expense.query.filter_by(expense_id=expense_id, user_id=user_id).first_or_404(
        description="Expense not found."
    )


@expense_bp.get("")
def list_expenses():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    result, errors = expense_query_for_user(user_id, request.args)
    if errors:
        return jsonify(success=False, message="Invalid expense filters.", errors=errors), 400
    query, pagination = result
    return jsonify(success=True, data=expense_list_response(query, pagination))


@expense_bp.get("/<int:expense_id>")
def get_expense(expense_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    return jsonify(success=True, data={"expense": _expense_or_404(expense_id, user_id).to_dict()})


@expense_bp.post("")
def create_expense():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    payload = request.get_json(silent=True)
    values, errors = validate_expense_payload(payload)
    if errors:
        return jsonify(success=False, message="Please correct the expense fields.", errors=errors), 400
    expense = Expense(user_id=user_id, **values)
    db.session.add(expense)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="The expense could not be saved. Check the selected category and amount."), 400
    return jsonify(success=True, message="Expense created.", data={"expense": expense.to_dict()}), 201


@expense_bp.put("/<int:expense_id>")
def update_expense(expense_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    expense = _expense_or_404(expense_id, user_id)
    values, errors = validate_expense_payload(request.get_json(silent=True), partial=True)
    if errors:
        return jsonify(success=False, message="Please correct the expense fields.", errors=errors), 400
    for field, value in values.items():
        setattr(expense, field, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="The expense could not be updated."), 400
    return jsonify(success=True, message="Expense updated.", data={"expense": expense.to_dict()})


@expense_bp.delete("/<int:expense_id>")
def delete_expense(expense_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    expense = _expense_or_404(expense_id, user_id)
    db.session.delete(expense)
    db.session.commit()
    return jsonify(success=True, message="Expense deleted.")