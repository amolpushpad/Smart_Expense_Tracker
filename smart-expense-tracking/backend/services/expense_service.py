from datetime import date
from decimal import Decimal, InvalidOperation
import re

from sqlalchemy import func, or_

from extensions import db
from models import Category, Expense

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("99999999.99")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OPTIONAL_TEXT_FIELDS = {"description": 500, "vendor": 160, "payment_method": 80}
EXPENSE_FIELDS = {"amount", "date", "category_id", *OPTIONAL_TEXT_FIELDS}
SORTS = {
    "newest": (Expense.date.desc(), Expense.expense_id.desc()),
    "oldest": (Expense.date.asc(), Expense.expense_id.asc()),
    "amount_high": (Expense.amount.desc(), Expense.date.desc()),
    "amount_low": (Expense.amount.asc(), Expense.date.desc()),
}


def validate_expense_payload(payload, partial=False):
    if not isinstance(payload, dict):
        return {}, {"body": "A JSON object is required."}

    errors = {}
    values = {}
    unknown_fields = payload.keys() - EXPENSE_FIELDS
    for field in unknown_fields:
        errors[field] = "This field is not supported."
    required = {"amount", "date", "category_id"}
    for field in required - payload.keys() if not partial else ():
        errors[field] = "This field is required."
    if partial and not payload:
        errors["body"] = "Provide at least one field to update."

    if "amount" in payload:
        raw_amount = payload["amount"]
        try:
            if isinstance(raw_amount, bool):
                raise InvalidOperation
            amount = Decimal(str(raw_amount))
            if not amount.is_finite() or amount <= 0 or amount > MAX_AMOUNT or amount.quantize(CENT) != amount:
                raise InvalidOperation
            values["amount"] = amount.quantize(CENT)
        except (InvalidOperation, ValueError, TypeError):
            errors["amount"] = "Amount must be a positive value with at most two decimal places."

    if "date" in payload:
        raw_date = payload["date"]
        try:
            if not isinstance(raw_date, str) or not DATE_PATTERN.fullmatch(raw_date):
                raise ValueError
            values["date"] = date.fromisoformat(raw_date)
        except ValueError:
            errors["date"] = "Enter a valid date in YYYY-MM-DD format."

    if "category_id" in payload:
        category_id = payload["category_id"]
        if isinstance(category_id, bool) or not str(category_id).isdigit() or int(category_id) < 1:
            errors["category_id"] = "Choose a valid category."
        elif not db.session.get(Category, int(category_id)):
            errors["category_id"] = "The selected category does not exist."
        else:
            values["category_id"] = int(category_id)

    for field, max_length in OPTIONAL_TEXT_FIELDS.items():
        if field in payload:
            value = payload[field]
            if value is None or value == "":
                values[field] = None
            elif not isinstance(value, str) or len(value.strip()) > max_length:
                errors[field] = f"{field.replace('_', ' ').capitalize()} must be at most {max_length} characters."
            else:
                values[field] = value.strip() or None

    return values, errors


def expense_query_for_user(user_id, params):
    query = Expense.query.filter(Expense.user_id == user_id)
    errors = {}

    search = params.get("search", "").strip()
    if len(search) > 200:
        errors["search"] = "Search must be at most 200 characters."
    elif search:
        pattern = f"%{search}%"
        query = query.filter(or_(Expense.description.ilike(pattern), Expense.vendor.ilike(pattern)))

    category_raw = params.get("category_id")
    if category_raw:
        if not category_raw.isdigit() or int(category_raw) < 1:
            errors["category_id"] = "Category ID must be a positive integer."
        else:
            query = query.filter(Expense.category_id == int(category_raw))

    dates = {}
    for parameter in ("start_date", "end_date"):
        raw_value = params.get(parameter)
        if raw_value:
            try:
                if not DATE_PATTERN.fullmatch(raw_value):
                    raise ValueError
                dates[parameter] = date.fromisoformat(raw_value)
            except ValueError:
                errors[parameter] = "Enter a valid date in YYYY-MM-DD format."
    if "start_date" in dates:
        query = query.filter(Expense.date >= dates["start_date"])
    if "end_date" in dates:
        query = query.filter(Expense.date <= dates["end_date"])
    if dates.get("start_date") and dates.get("end_date") and dates["start_date"] > dates["end_date"]:
        errors["date_range"] = "Start date must be on or before end date."

    amounts = {}
    for parameter in ("min_amount", "max_amount"):
        raw_value = params.get(parameter)
        if raw_value:
            try:
                amount = Decimal(raw_value)
                if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT or amount.quantize(CENT) != amount:
                    raise InvalidOperation
                amounts[parameter] = amount.quantize(CENT)
            except (InvalidOperation, ValueError):
                errors[parameter] = "Enter a non-negative amount with at most two decimal places."
    if "min_amount" in amounts:
        query = query.filter(Expense.amount >= amounts["min_amount"])
    if "max_amount" in amounts:
        query = query.filter(Expense.amount <= amounts["max_amount"])
    if "min_amount" in amounts and "max_amount" in amounts and amounts["min_amount"] > amounts["max_amount"]:
        errors["amount_range"] = "Minimum amount must be less than or equal to maximum amount."

    sort = params.get("sort", "newest")
    if sort not in SORTS:
        errors["sort"] = "Sort must be newest, oldest, amount_high, or amount_low."

    pagination = {}
    for parameter, default, maximum in (("page", 1, 100000), ("per_page", 20, 100)):
        raw_value = params.get(parameter, str(default))
        if not raw_value.isdigit() or int(raw_value) < 1 or int(raw_value) > maximum:
            errors[parameter] = f"{parameter.replace('_', ' ').capitalize()} must be between 1 and {maximum}."
        else:
            pagination[parameter] = int(raw_value)

    if errors:
        return None, errors
    return (query.order_by(*SORTS[sort]), pagination), None


def expense_list_response(query, pagination):
    total = query.order_by(None).count()
    total_amount = query.order_by(None).with_entities(func.coalesce(func.sum(Expense.amount), 0)).scalar()
    items = query.offset((pagination["page"] - 1) * pagination["per_page"]).limit(pagination["per_page"]).all()
    return {
        "expenses": [expense.to_dict() for expense in items],
        "pagination": {
            **pagination,
            "total": total,
            "pages": (total + pagination["per_page"] - 1) // pagination["per_page"],
        },
        "total_amount": format(Decimal(total_amount), ".2f"),
    }