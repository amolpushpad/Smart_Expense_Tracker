import logging
import math

from flask import Blueprint, jsonify, request

from services.synthetic_demo_service import (
    estimate_synthetic_monthly_expenses,
    synthetic_model_evaluation,
    synthetic_snapshot_analytics,
)

logger = logging.getLogger(__name__)
demo_bp = Blueprint("synthetic_demo", __name__)
PROFILE_FIELDS = {
    "age",
    "monthly_income_inr",
    "savings_inr",
    "employment_status",
    "has_loan",
}


@demo_bp.get("/analytics")
def analytics():
    try:
        result = synthetic_snapshot_analytics()
    except ValueError as error:
        return jsonify(success=False, message=str(error)), 503
    except Exception:
        logger.exception("Synthetic dataset analytics failed")
        return jsonify(success=False, message="Synthetic dataset analytics are temporarily unavailable."), 503
    return jsonify(success=True, data=result)


@demo_bp.get("/ml/evaluation")
def model_evaluation():
    try:
        result = synthetic_model_evaluation()
    except ValueError as error:
        return jsonify(success=False, message=str(error)), 503
    except Exception:
        logger.exception("Synthetic dataset model evaluation failed")
        return jsonify(success=False, message="Synthetic dataset model evaluation is temporarily unavailable."), 503
    return jsonify(success=True, data=result)


@demo_bp.post("/ml/estimate-monthly-expenses")
def estimate_monthly_expenses():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(success=False, message="A JSON object is required."), 400
    errors = {field: "This field is not supported." for field in payload.keys() - PROFILE_FIELDS}
    for field in ("age", "monthly_income_inr", "savings_inr"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            errors[field] = "Provide a finite number."
    if "age" not in errors and not 18 <= payload["age"] <= 120:
        errors["age"] = "Age must be between 18 and 120."
    for field in ("monthly_income_inr", "savings_inr"):
        if field not in errors and not 0 <= payload[field] <= 1_000_000_000_000:
            errors[field] = "Amount must be between 0 and 1,000,000,000,000 INR."
    employment = payload.get("employment_status")
    if not isinstance(employment, str) or not employment.strip() or len(employment) > 50:
        errors["employment_status"] = "Choose a valid employment status."
    has_loan = payload.get("has_loan")
    if not isinstance(has_loan, bool):
        errors["has_loan"] = "has_loan must be true or false."
    if errors:
        return jsonify(success=False, message="Please correct the synthetic profile fields.", errors=errors), 400

    profile = {
        "age": int(payload["age"]),
        "monthly_income_inr": float(payload["monthly_income_inr"]),
        "savings_inr": float(payload["savings_inr"]),
        "employment_status": employment.strip(),
        "has_loan": has_loan,
    }
    try:
        result = estimate_synthetic_monthly_expenses(profile)
    except ValueError as error:
        return jsonify(success=False, message=str(error)), 503
    except Exception:
        logger.exception("Synthetic monthly-expense estimate failed")
        return jsonify(success=False, message="Synthetic monthly-expense estimate is temporarily unavailable."), 503
    return jsonify(success=True, data=result)
