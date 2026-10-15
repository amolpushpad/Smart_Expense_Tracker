from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Income, User
from services.income_service import income_list_response, income_query_for_user, validate_income_payload

income_bp = Blueprint("income", __name__)


def _user_id():
    user_id = session.get("user_id")
    return user_id if user_id and db.session.get(User, user_id) else None


def _income_or_404(income_id, user_id):
    return Income.query.filter_by(income_id=income_id, user_id=user_id).first_or_404(
        description="Income record not found."
    )


@income_bp.get("")
def list_income():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    query, errors = income_query_for_user(user_id, request.args)
    if errors:
        return jsonify(success=False, message="Invalid income filters.", errors=errors), 400
    return jsonify(success=True, data=income_list_response(query))


@income_bp.get("/<int:income_id>")
def get_income(income_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    return jsonify(success=True, data={"income": _income_or_404(income_id, user_id).to_dict()})


@income_bp.post("")
def create_income():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    values, errors = validate_income_payload(request.get_json(silent=True))
    if errors:
        return jsonify(success=False, message="Please correct the income fields.", errors=errors), 400
    income = Income(user_id=user_id, **values)
    db.session.add(income)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="The income record could not be saved."), 400
    return jsonify(success=True, message="Income record created.", data={"income": income.to_dict()}), 201


@income_bp.put("/<int:income_id>")
def update_income(income_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    income = _income_or_404(income_id, user_id)
    values, errors = validate_income_payload(request.get_json(silent=True), partial=True)
    if errors:
        return jsonify(success=False, message="Please correct the income fields.", errors=errors), 400
    for field, value in values.items():
        setattr(income, field, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="The income record could not be updated."), 400
    return jsonify(success=True, message="Income record updated.", data={"income": income.to_dict()})


@income_bp.delete("/<int:income_id>")
def delete_income(income_id):
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    db.session.delete(_income_or_404(income_id, user_id))
    db.session.commit()
    return jsonify(success=True, message="Income record deleted.")
