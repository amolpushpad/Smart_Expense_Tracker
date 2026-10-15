from datetime import date

from flask import Blueprint, jsonify, request, session

from extensions import db
from models import User
from services.dashboard_service import (
    budget_progress,
    category_breakdown,
    dashboard_summary,
    monthly_trends,
    recent_transactions,
)

dashboard_bp = Blueprint("dashboard", __name__)


def _user_id():
    user_id = session.get("user_id")
    return user_id if user_id and db.session.get(User, user_id) else None


def _period():
    today = date.today()
    month_raw = request.args.get("month", str(today.month))
    year_raw = request.args.get("year", str(today.year))
    if not month_raw.isdigit() or not 1 <= int(month_raw) <= 12:
        return None, None, {"month": "Month must be an integer from 1 to 12."}
    if not year_raw.isdigit() or not 1900 <= int(year_raw) <= 9999:
        return None, None, {"year": "Year must be between 1900 and 9999."}
    return int(month_raw), int(year_raw), None


def _require_user():
    user_id = _user_id()
    if not user_id:
        return None, (jsonify(success=False, message="Authentication required."), 401)
    return user_id, None


def _validated_period(user_id):
    month, year, errors = _period()
    if errors:
        return None, None, (jsonify(success=False, message="Invalid dashboard period.", errors=errors), 400)
    return month, year, None


@dashboard_bp.get("/summary")
def summary():
    user_id, error_response = _require_user()
    if error_response:
        return error_response
    month, year, error_response = _validated_period(user_id)
    if error_response:
        return error_response
    return jsonify(success=True, data={"summary": dashboard_summary(user_id, month, year)})


@dashboard_bp.get("/recent-transactions")
def get_recent_transactions():
    user_id, error_response = _require_user()
    if error_response:
        return error_response
    raw_limit = request.args.get("limit", "10")
    if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= 50:
        return jsonify(success=False, message="Invalid transaction limit.", errors={"limit": "Limit must be from 1 to 50."}), 400
    return jsonify(success=True, data={"transactions": recent_transactions(user_id, int(raw_limit))})


@dashboard_bp.get("/monthly-trends")
def get_monthly_trends():
    user_id, error_response = _require_user()
    if error_response:
        return error_response
    month, year, error_response = _validated_period(user_id)
    if error_response:
        return error_response
    return jsonify(success=True, data={"months": monthly_trends(user_id, month, year)})


@dashboard_bp.get("/category-breakdown")
def get_category_breakdown():
    user_id, error_response = _require_user()
    if error_response:
        return error_response
    month, year, error_response = _validated_period(user_id)
    if error_response:
        return error_response
    return jsonify(success=True, data={"period": {"month": month, "year": year}, "categories": category_breakdown(user_id, month, year)})


@dashboard_bp.get("/budget-progress")
def get_budget_progress():
    user_id, error_response = _require_user()
    if error_response:
        return error_response
    month, year, error_response = _validated_period(user_id)
    if error_response:
        return error_response
    return jsonify(success=True, data={"period": {"month": month, "year": year}, "budgets": budget_progress(user_id, month, year)})
