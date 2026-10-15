from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Budget, User
from services.budget_service import budget_list_response, budget_query_for_user, budget_to_dict, validate_budget_payload

budget_bp = Blueprint("budgets", __name__)


def _user_id():
    user_id = session.get("user_id")
    return user_id if user_id and db.session.get(User, user_id) else None


def _budget_or_404(budget_id, user_id):
    return Budget.query.filter_by(budget_id=budget_id, user_id=user_id).first_or_404(
        description="Budget not found."
    )


@budget_bp.get("")
def list_budgets():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    query, errors = budget_query_for_user(user_id, request.args)
    if errors:
        return jsonify(success=False, message="Invalid budget filters.", errors=errors), 400
    return jsonify(success=True, data=budget_list_response(query))


@budget_bp.get("/<int:budget_id>")
def get_budget(budget_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    return jsonify(success=True, data={"budget": budget_to_dict(_budget_or_404(budget_id, user_id))})


@budget_bp.post("")
def create_budget():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    values, errors = validate_budget_payload(request.get_json(silent=True))
    if errors:
        return jsonify(success=False, message="Please correct the budget fields.", errors=errors), 400
    budget = Budget(user_id=user_id, **values)
    db.session.add(budget)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="A budget already exists for this category and period."), 409
    return jsonify(success=True, message="Budget created.", data={"budget": budget_to_dict(budget)}), 201


@budget_bp.put("/<int:budget_id>")
def update_budget(budget_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    budget = _budget_or_404(budget_id, user_id)
    values, errors = validate_budget_payload(request.get_json(silent=True), partial=True)
    if errors:
        return jsonify(success=False, message="Please correct the budget fields.", errors=errors), 400
    for field, value in values.items():
        setattr(budget, field, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="A budget already exists for this category and period."), 409
    return jsonify(success=True, message="Budget updated.", data={"budget": budget_to_dict(budget)})


@budget_bp.delete("/<int:budget_id>")
def delete_budget(budget_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    db.session.delete(_budget_or_404(budget_id, user_id))
    db.session.commit()
    return jsonify(success=True, message="Budget deleted.")
