import csv
from io import StringIO

from flask import Blueprint, Response, jsonify, request, session

from extensions import db
from models import User
from services.analytics_service import analytics_report, date_period_for_request

analytics_bp = Blueprint("analytics", __name__)


def _user_id():
    user_id = session.get("user_id")
    return user_id if user_id and db.session.get(User, user_id) else None


def _period_or_error():
    period, errors = date_period_for_request(request.args)
    if errors:
        return None, (jsonify(success=False, message="Invalid analytics date range.", errors=errors), 400)
    return period, None


@analytics_bp.get("")
def get_analytics():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    period, error_response = _period_or_error()
    if error_response:
        return error_response
    return jsonify(success=True, data=analytics_report(user_id, period))


def _csv_safe(value):
    text = str(value or "")
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@analytics_bp.get("/export.csv")
def export_analytics_csv():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    period, error_response = _period_or_error()
    if error_response:
        return error_response

    report = analytics_report(user_id, period)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "record_type",
        "date",
        "category",
        "description",
        "income",
        "expense",
        "total_income",
        "total_expenses",
        "savings",
        "balance",
        "period_start",
        "period_end",
    ])
    summary = report["summary"]
    for transaction in report["transactions"]:
        writer.writerow([
            transaction["transaction_type"],
            transaction["date"],
            _csv_safe(transaction["category"]),
            _csv_safe(transaction["description"]),
            transaction["income"],
            transaction["expense"],
            "",
            "",
            "",
            "",
            report["period"]["start_date"],
            report["period"]["end_date"],
        ])
    writer.writerow([
        "summary",
        "",
        "",
        report["period"]["label"],
        "",
        "",
        summary["total_income"],
        summary["total_expenses"],
        summary["savings"],
        summary["balance"],
        report["period"]["start_date"],
        report["period"]["end_date"],
    ])
    response = Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="financial-report.csv"'
    response.headers["Cache-Control"] = "no-store"
    return response
