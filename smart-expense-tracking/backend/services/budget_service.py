from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func

from extensions import db
from models import Budget, Category, Expense

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("99999999.99")
BUDGET_FIELDS = {"amount", "category_id", "month", "year"}


def _positive_integer(value):
    return not isinstance(value, bool) and str(value).isdigit() and int(value) > 0


def validate_budget_payload(payload, partial=False):
    if not isinstance(payload, dict):
        return {}, {"body": "A JSON object is required."}

    errors = {field: "This field is not supported." for field in payload.keys() - BUDGET_FIELDS}
    required = {"amount", "month", "year"}
    for field in (required - payload.keys()) if not partial else ():
        errors[field] = "This field is required."
    if partial and not payload:
        errors["body"] = "Provide at least one field to update."

    values = {}
    if "amount" in payload:
        try:
            raw_amount = payload["amount"]
            if isinstance(raw_amount, bool):
                raise InvalidOperation
            amount = Decimal(str(raw_amount))
            if not amount.is_finite() or amount <= 0 or amount > MAX_AMOUNT or amount.quantize(CENT) != amount:
                raise InvalidOperation
            values["amount"] = amount.quantize(CENT)
        except (InvalidOperation, ValueError, TypeError):
            errors["amount"] = "Amount must be positive with at most two decimal places."

    if "month" in payload:
        month = payload["month"]
        if not _positive_integer(month) or not 1 <= int(month) <= 12:
            errors["month"] = "Month must be an integer from 1 to 12."
        else:
            values["month"] = int(month)

    if "year" in payload:
        year = payload["year"]
        if not _positive_integer(year) or not 1900 <= int(year) <= 9999:
            errors["year"] = "Year must be an integer from 1900 to 9999."
        else:
            values["year"] = int(year)

    if "category_id" in payload:
        category_id = payload["category_id"]
        if category_id is None or category_id == "":
            values["category_id"] = None
        elif not _positive_integer(category_id):
            errors["category_id"] = "Choose a valid category or overall budget."
        elif not db.session.get(Category, int(category_id)):
            errors["category_id"] = "The selected category does not exist."
        else:
            values["category_id"] = int(category_id)

    return values, errors


def budget_query_for_user(user_id, params):
    query = Budget.query.filter(Budget.user_id == user_id)
    errors = {}
    period = {}
    for parameter, lower, upper in (("month", 1, 12), ("year", 1900, 9999)):
        raw_value = params.get(parameter)
        if raw_value is not None:
            if not _positive_integer(raw_value) or not lower <= int(raw_value) <= upper:
                errors[parameter] = f"{parameter.capitalize()} must be between {lower} and {upper}."
            else:
                period[parameter] = int(raw_value)
    if bool(period) and len(period) != 2:
        errors["period"] = "Month and year must be provided together."
    if len(period) == 2:
        query = query.filter(Budget.month == period["month"], Budget.year == period["year"])
    if errors:
        return None, errors
    return query.order_by(Budget.category_id.asc(), Budget.budget_id.asc()), None


def budget_to_dict(budget):
    first_day = date(budget.year, budget.month, 1)
    last_day = date(budget.year, budget.month, monthrange(budget.year, budget.month)[1])
    spending = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.user_id == budget.user_id,
        Expense.date >= first_day,
        Expense.date <= last_day,
    )
    if budget.category_id is not None:
        spending = spending.filter(Expense.category_id == budget.category_id)
    amount = Decimal(spending.scalar())
    return budget.to_dict(amount)


def budget_list_response(query):
    records = query.all()
    return {"budgets": [budget_to_dict(budget) for budget in records]}
