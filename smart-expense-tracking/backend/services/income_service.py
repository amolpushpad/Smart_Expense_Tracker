from datetime import date
from decimal import Decimal, InvalidOperation
import re

from sqlalchemy import func

from models import Income

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("99999999.99")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INCOME_FIELDS = {"source", "amount", "date", "description"}
SORTS = {
    "newest": (Income.date.desc(), Income.income_id.desc()),
    "oldest": (Income.date.asc(), Income.income_id.asc()),
    "amount_high": (Income.amount.desc(), Income.date.desc()),
    "amount_low": (Income.amount.asc(), Income.date.desc()),
}


def validate_income_payload(payload, partial=False):
    if not isinstance(payload, dict):
        return {}, {"body": "A JSON object is required."}

    errors = {field: "This field is not supported." for field in payload.keys() - INCOME_FIELDS}
    required = {"source", "amount", "date"}
    for field in (required - payload.keys()) if not partial else ():
        errors[field] = "This field is required."
    if partial and not payload:
        errors["body"] = "Provide at least one field to update."

    values = {}
    if "source" in payload:
        source = payload["source"]
        if not isinstance(source, str) or not source.strip() or len(source.strip()) > 120:
            errors["source"] = "Source must contain 1 to 120 characters."
        else:
            values["source"] = source.strip()

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

    if "date" in payload:
        try:
            raw_date = payload["date"]
            if not isinstance(raw_date, str) or not DATE_PATTERN.fullmatch(raw_date):
                raise ValueError
            values["date"] = date.fromisoformat(raw_date)
        except ValueError:
            errors["date"] = "Enter a valid date in YYYY-MM-DD format."

    if "description" in payload:
        description = payload["description"]
        if description is None or description == "":
            values["description"] = None
        elif not isinstance(description, str) or len(description.strip()) > 500:
            errors["description"] = "Description must be at most 500 characters."
        else:
            values["description"] = description.strip() or None

    return values, errors


def income_query_for_user(user_id, params):
    query = Income.query.filter(Income.user_id == user_id)
    errors = {}
    parsed_dates = {}
    for parameter in ("start_date", "end_date"):
        raw_value = params.get(parameter)
        if raw_value:
            try:
                if not DATE_PATTERN.fullmatch(raw_value):
                    raise ValueError
                parsed_dates[parameter] = date.fromisoformat(raw_value)
            except ValueError:
                errors[parameter] = "Enter a valid date in YYYY-MM-DD format."
    if "start_date" in parsed_dates:
        query = query.filter(Income.date >= parsed_dates["start_date"])
    if "end_date" in parsed_dates:
        query = query.filter(Income.date <= parsed_dates["end_date"])
    if (
        parsed_dates.get("start_date")
        and parsed_dates.get("end_date")
        and parsed_dates["start_date"] > parsed_dates["end_date"]
    ):
        errors["date_range"] = "Start date must be on or before end date."

    sort = params.get("sort", "newest")
    if sort not in SORTS:
        errors["sort"] = "Sort must be newest, oldest, amount_high, or amount_low."

    if errors:
        return None, errors
    return query.order_by(*SORTS[sort]), None


def income_list_response(query):
    total_amount = query.order_by(None).with_entities(func.coalesce(func.sum(Income.amount), 0)).scalar()
    records = query.all()
    return {
        "incomes": [income.to_dict() for income in records],
        "total_amount": format(Decimal(total_amount), ".2f"),
    }
