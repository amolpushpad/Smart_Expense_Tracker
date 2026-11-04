from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Category, User
from services.expense_service import validate_expense_payload
from services.csv_import_service import (
    MAX_CSV_BYTES,
    MAX_CSV_ROWS,
    CsvImportError,
    build_expense,
    classify_duplicates,
    parse_csv_rows,
    preview_summary,
    validate_csv_rows,
)

expense_import_bp = Blueprint("expense_import", __name__)


def _user_id():
    user_id = session.get("user_id")
    return user_id if user_id and db.session.get(User, user_id) else None


def _read_csv_upload():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        raise CsvImportError("Choose a CSV file to upload.")
    if not upload.filename.lower().endswith(".csv"):
        raise CsvImportError("Choose a file with the .csv extension.")
    contents = upload.stream.read(MAX_CSV_BYTES + 1)
    if len(contents) > MAX_CSV_BYTES:
        raise CsvImportError("CSV files must be 5 MB or smaller.", 413)
    return contents


def _preview_data(user_id, contents):
    rows = validate_csv_rows(parse_csv_rows(contents))
    classify_duplicates(user_id, rows)
    return {
        "summary": preview_summary(rows),
        "rows": [
            {
                "row_number": row["row_number"],
                "data": row["data"],
                "errors": row["errors"],
                "potential_duplicate": row["potential_duplicate"],
                "duplicate_of": row["duplicate_of"],
                "duplicate_reason": row["duplicate_reason"],
            }
            for row in rows
        ],
    }


@expense_import_bp.post("/import/preview")
def preview_expense_import():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401
    try:
        data = _preview_data(user_id, _read_csv_upload())
    except CsvImportError as error:
        return jsonify(success=False, message=str(error)), error.status_code
    return jsonify(success=True, data=data)


@expense_import_bp.post("/import/confirm")
def confirm_expense_import():
    user_id = _user_id()
    if not user_id:
        return jsonify(success=False, message="Authentication required."), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"rows"} or not isinstance(payload["rows"], list):
        return jsonify(success=False, message="A list of approved transaction rows is required."), 400
    if not payload["rows"]:
        return jsonify(success=False, message="Select at least one valid row to import."), 400
    if len(payload["rows"]) > MAX_CSV_ROWS:
        return jsonify(success=False, message=f"At most {MAX_CSV_ROWS} transaction rows may be imported at once."), 413

    categories = {
        category.category_name.casefold(): category
        for category in Category.query.order_by(Category.category_id.asc()).all()
    }
    rows = []
    errors = []
    for index, approved_row in enumerate(payload["rows"], start=1):
        if not isinstance(approved_row, dict) or set(approved_row) - {
            "date", "amount", "category", "description", "vendor", "allow_duplicate",
        }:
            errors.append({"row_number": index, "errors": {"row": "The approved row has unsupported fields."}})
            continue
        allow_duplicate = approved_row.get("allow_duplicate", False)
        if not isinstance(allow_duplicate, bool):
            errors.append({"row_number": index, "errors": {"row": "Duplicate approval must be a boolean value."}})
            continue
        category_name = approved_row.get("category")
        category = categories.get(category_name.casefold()) if isinstance(category_name, str) else None
        if not category:
            errors.append({"row_number": index, "errors": {"category": "The selected category no longer exists."}})
            continue

        values, row_errors = validate_expense_payload({
            "amount": approved_row.get("amount"),
            "date": approved_row.get("date"),
            "category_id": category.category_id,
            "description": approved_row.get("description"),
            "vendor": approved_row.get("vendor"),
        })
        if row_errors:
            errors.append({"row_number": index, "errors": row_errors})
            continue
        rows.append({
            "row_number": index,
            "values": values,
            "category_id": category.category_id,
            "allow_duplicate": allow_duplicate,
            "potential_duplicate": False,
            "duplicate_of": None,
            "duplicate_reason": None,
            "errors": {},
            "data": {},
        })

    if errors:
        return jsonify(success=False, message="Some approved rows are no longer valid. Preview the CSV again.", errors=errors), 400

    classify_duplicates(user_id, rows)
    unapproved_duplicates = [
        {
            "row_number": row["row_number"],
            "duplicate_of": row["duplicate_of"],
            "reason": row["duplicate_reason"],
        }
        for row in rows
        if row["potential_duplicate"] and not row["allow_duplicate"]
    ]
    if unapproved_duplicates:
        return jsonify(
            success=False,
            message="Some rows now match existing transactions. Preview the CSV again before importing.",
            data={"duplicates": unapproved_duplicates},
        ), 409

    try:
        db.session.add_all(build_expense(row, user_id) for row in rows)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(success=False, message="The transactions could not be imported. No rows were saved."), 503

    return jsonify(
        success=True,
        message="Transactions imported.",
        data={"imported": len(rows)},
    ), 201
