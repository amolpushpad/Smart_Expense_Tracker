import csv
import re
from datetime import date
from decimal import Decimal
from io import StringIO

from models import Category, Expense
from services.expense_service import validate_expense_payload

MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 5000
REQUIRED_COLUMNS = {"date", "amount", "category"}
OPTIONAL_COLUMNS = {"description", "vendor"}
TOKEN_PATTERN = re.compile(r"[^a-z0-9]+")


class CsvImportError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def parse_csv_rows(contents):
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvImportError("The CSV file must use UTF-8 text encoding.") from error

    reader = csv.reader(StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration as error:
        raise CsvImportError("The CSV file is empty.") from error
    except csv.Error as error:
        raise CsvImportError("The CSV header is malformed.") from error

    columns = [column.strip().lower() for column in header]
    if any(not column for column in columns):
        raise CsvImportError("Every CSV column must have a name.")
    if len(columns) != len(set(columns)):
        raise CsvImportError("The CSV contains duplicate column names.")
    unsupported = set(columns) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
    if unsupported:
        raise CsvImportError(f"Unsupported CSV columns: {', '.join(sorted(unsupported))}.")
    missing = REQUIRED_COLUMNS - set(columns)
    if missing:
        raise CsvImportError(f"Missing required CSV columns: {', '.join(sorted(missing))}.")

    rows = []
    try:
        for values in reader:
            if not any(value.strip() for value in values):
                continue
            row_number = reader.line_num
            if len(rows) >= MAX_CSV_ROWS:
                raise CsvImportError(f"CSV files may contain at most {MAX_CSV_ROWS} transaction rows.", 413)
            row = {
                column: values[index].strip() if index < len(values) else ""
                for index, column in enumerate(columns)
            }
            rows.append({
                "row_number": row_number,
                "raw": row,
                "shape_error": (
                    f"Expected {len(columns)} columns but found {len(values)}."
                    if len(values) != len(columns)
                    else None
                ),
            })
    except csv.Error as error:
        raise CsvImportError("The CSV contains malformed quoting or rows.") from error

    if not rows:
        raise CsvImportError("The CSV contains no transaction rows.")
    return rows


def validate_csv_rows(rows):
    categories = {
        category.category_name.casefold(): category
        for category in Category.query.order_by(Category.category_id.asc()).all()
    }
    validated = []
    for row in rows:
        raw = row["raw"]
        errors = {}
        values = {}
        category_name = raw.get("category", "")
        category = categories.get(category_name.casefold())

        if row["shape_error"]:
            errors["row"] = row["shape_error"]
        if not category_name:
            errors["category"] = "Category is required."
        elif not category:
            errors["category"] = f"Category '{category_name[:80]}' does not exist."
        values, field_errors = validate_expense_payload({
            "amount": raw.get("amount", ""),
            "date": raw.get("date", ""),
            "category_id": category.category_id if category else 0,
            "description": raw.get("description", ""),
            "vendor": raw.get("vendor", ""),
        })
        field_errors.pop("category_id", None)
        if field_errors:
            errors.update({
                ("category" if field == "category_id" else field): message
                for field, message in field_errors.items()
            })
        if row["shape_error"] or not category:
            values = {}
        data = {
            "date": values["date"].isoformat() if "date" in values else raw.get("date", ""),
            "amount": format(values["amount"], ".2f") if "amount" in values else raw.get("amount", ""),
            "category": category.category_name if category else category_name,
            "description": values.get("description") or "",
            "vendor": values.get("vendor") or "",
        }
        validated.append({
            "row_number": row["row_number"],
            "data": data,
            "values": values,
            "category_id": category.category_id if category else None,
            "errors": errors,
            "potential_duplicate": False,
            "duplicate_of": None,
            "duplicate_reason": None,
        })
    return validated


def _normalized_text(value):
    return TOKEN_PATTERN.sub(" ", (value or "").casefold()).strip()


def _duplicate_reasons(left, right):
    if (
        left["date"] != right["date"]
        or left["category_id"] != right["category_id"]
        or left["amount"] != right["amount"]
    ):
        return []

    left_description = _normalized_text(left["description"])
    right_description = _normalized_text(right["description"])
    left_vendor = _normalized_text(left["vendor"])
    right_vendor = _normalized_text(right["vendor"])
    reasons = []
    if left_description and left_description == right_description:
        reasons.append("normalized description matches")
    if left_vendor and left_vendor == right_vendor and (
        not left_description or not right_description or left_description == right_description
    ):
        reasons.append("normalized vendor matches")
    return reasons


def classify_duplicates(user_id, rows):
    valid_rows = [row for row in rows if not row["errors"]]
    if not valid_rows:
        return

    dates = sorted({row["values"]["date"] for row in valid_rows})
    existing_expenses = []
    for start in range(0, len(dates), 400):
        existing_expenses.extend(Expense.query.filter(
            Expense.user_id == user_id,
            Expense.date.in_(dates[start:start + 400]),
        ).all())

    candidates = {}
    for expense in existing_expenses:
        key = (expense.date, expense.category_id, expense.amount)
        candidates.setdefault(key, []).append({
            "date": expense.date,
            "category_id": expense.category_id,
            "amount": expense.amount,
            "description": expense.description,
            "vendor": expense.vendor,
            "duplicate_of": {"type": "expense", "id": expense.expense_id},
        })

    for row in valid_rows:
        values = row["values"]
        key = (values["date"], row["category_id"], values["amount"])
        transaction = {
            "date": values["date"],
            "category_id": row["category_id"],
            "amount": values["amount"],
            "description": values.get("description"),
            "vendor": values.get("vendor"),
        }
        matching = next(
            (
                (candidate, reasons)
                for candidate in candidates.get(key, [])
                if (reasons := _duplicate_reasons(transaction, candidate))
            ),
            None,
        )
        if matching:
            candidate, reasons = matching
            row["potential_duplicate"] = True
            row["duplicate_of"] = candidate["duplicate_of"]
            row["duplicate_reason"] = ", ".join(reasons)
        candidates.setdefault(key, []).append({
            **transaction,
            "duplicate_of": {"type": "row", "row_number": row["row_number"]},
        })


def preview_summary(rows):
    valid_rows = [row for row in rows if not row["errors"]]
    total_amount = sum((row["values"]["amount"] for row in valid_rows), Decimal("0.00"))
    return {
        "rows_total": len(rows),
        "valid_rows": len(valid_rows),
        "invalid_rows": len(rows) - len(valid_rows),
        "duplicate_rows": sum(row["potential_duplicate"] for row in valid_rows),
        "total_amount": format(total_amount, ".2f"),
        "sample_transactions": [row["data"] for row in valid_rows[:5]],
    }


def build_expense(row, user_id):
    return Expense(user_id=user_id, **row["values"])
