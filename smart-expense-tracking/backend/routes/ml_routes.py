import logging
from calendar import monthrange
from datetime import date

from flask import Blueprint, jsonify, request, session

from extensions import db
from models import User
from services.analytics_service import analytics_report
from services.anomaly_service import detect_unusual_expenses
from services.categorization_service import suggest_category
from services.duplicate_service import find_possible_duplicates
from services.prediction_service import predict_monthly_spending

logger = logging.getLogger(__name__)
ml_bp = Blueprint("ml", __name__)
TEXT_FIELDS = {"description": 500, "vendor": 160}


def _user_id():
    user_id = session.get("user_id")
    return user_id if user_id and db.session.get(User, user_id) else None


def _validated_period():
    today = date.today()
    month_raw = request.args.get("month", str(today.month))
    year_raw = request.args.get("year", str(today.year))
    errors = {}
    if not month_raw.isdigit() or not 1 <= int(month_raw) <= 12:
        errors["month"] = "Month must be an integer from 1 to 12."
    if not year_raw.isdigit() or not 1900 <= int(year_raw) <= 9999:
        errors["year"] = "Year must be between 1900 and 9999."
    if errors:
        return None, (jsonify(success=False, message="Invalid prediction period.", errors=errors), 400)
    return (int(month_raw), int(year_raw)), None


@ml_bp.post("/categorize")
def categorize():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(success=False, message="A JSON object is required."), 400
    errors = {field: "This field is not supported." for field in payload.keys() - TEXT_FIELDS.keys()}
    values = {}
    for field, maximum in TEXT_FIELDS.items():
        value = payload.get(field, "")
        if value is None and field == "vendor":
            value = ""
        if not isinstance(value, str) or len(value.strip()) > maximum:
            errors[field] = f"{field.capitalize()} must be at most {maximum} characters."
        else:
            values[field] = value.strip()
    if not values.get("description") and not values.get("vendor"):
        errors["description"] = "Provide a description or vendor."
    if errors:
        return jsonify(success=False, message="Please correct the categorization input.", errors=errors), 400

    try:
        suggestion = suggest_category(values["description"], values["vendor"])
    except Exception:
        logger.exception("Expense categorization failed for authenticated user %s", user_id)
        return jsonify(success=False, message="Category suggestions are temporarily unavailable."), 503
    return jsonify(success=True, data=suggestion)


@ml_bp.get("/prediction")
def prediction():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    period, error_response = _validated_period()
    if error_response:
        return error_response
    try:
        result = predict_monthly_spending(user_id, period[0], period[1])
    except Exception:
        logger.exception("Spending prediction failed for authenticated user %s", user_id)
        return jsonify(success=False, message="Spending prediction is temporarily unavailable."), 503
    return jsonify(success=True, data={"prediction": result})


@ml_bp.get("/anomalies")
def anomalies():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    try:
        result = detect_unusual_expenses(user_id)
    except Exception:
        logger.exception("Unusual-spending analysis failed for authenticated user %s", user_id)
        return jsonify(success=False, message="Unusual-spending analysis is temporarily unavailable."), 503
    return jsonify(success=True, data={"anomalies": result})


@ml_bp.get("/duplicates")
def duplicates():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    try:
        result = find_possible_duplicates(user_id)
    except Exception:
        logger.exception("Possible-duplicate analysis failed for authenticated user %s", user_id)
        return jsonify(success=False, message="Possible-duplicate analysis is temporarily unavailable."), 503
    return jsonify(success=True, data={"duplicates": result})


def _run_insight(user_id, feature, operation, data, errors):
    try:
        data[feature] = operation()
    except Exception:
        logger.exception("%s insight failed for authenticated user %s", feature, user_id)
        db.session.rollback()
        errors[feature] = f"{feature.replace('_', ' ').capitalize()} insights are temporarily unavailable."


@ml_bp.get("/insights")
def insights():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    period, error_response = _validated_period()
    if error_response:
        return error_response
    month, year = period
    data = {}
    errors = {}
    _run_insight(
        user_id,
        "prediction",
        lambda: predict_monthly_spending(user_id, month, year),
        data,
        errors,
    )
    _run_insight(
        user_id,
        "anomalies",
        lambda: detect_unusual_expenses(user_id),
        data,
        errors,
    )
    _run_insight(
        user_id,
        "duplicates",
        lambda: find_possible_duplicates(user_id),
        data,
        errors,
    )

    def pattern_observations():
        report = analytics_report(
            user_id,
            {
                "kind": "monthly",
                "month": month,
                "year": year,
                "start": date(year, month, 1),
                "end": date(year, month, monthrange(year, month)[1]),
            },
        )
        patterns = []
        highest = report["highest_spending_category"]
        if highest:
            patterns.append({
                "type": "category",
                "message": f"Highest spending category is {highest['category_name']} ({highest['amount']}).",
                "method": "historical_aggregation",
            })
        comparison = report["previous_period"]
        if comparison["change_percentage"] is not None:
            change = float(comparison["change_percentage"])
            if change > 0:
                patterns.append({
                    "type": "trend",
                    "message": f"Spending increased {change:.2f}% versus the previous month.",
                    "method": "period_comparison",
                })
            elif change < 0:
                patterns.append({
                    "type": "trend",
                    "message": f"Spending decreased {abs(change):.2f}% versus the previous month.",
                    "method": "period_comparison",
                })
        budget = report["budget"]
        if budget and budget["budget_utilization"] is not None and float(budget["budget_utilization"]) >= 80:
            patterns.append({
                "type": "budget",
                "message": f"Monthly budget utilization is {budget['budget_utilization']}%.",
                "method": "budget_calculation",
            })
        return patterns

    _run_insight(user_id, "spending_patterns", pattern_observations, data, errors)
    data["errors"] = errors
    return jsonify(success=True, data=data)
