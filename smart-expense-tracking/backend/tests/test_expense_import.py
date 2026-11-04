from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import create_app
from extensions import db
from models import Category, Expense, User
from services.csv_import_service import MAX_CSV_BYTES, MAX_CSV_ROWS


class TestConfig:
    TESTING = True
    SECRET_KEY = "expense-import-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ["http://localhost:5173"]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    ADMIN_EMAILS = set()


@pytest.fixture
def app():
    test_app = create_app(TestConfig)
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _csrf_headers(client):
    response = client.get("/api/auth/csrf")
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def _authenticated(client, email="import@example.com"):
    client.post(
        "/api/auth/register",
        json={"name": "Import User", "email": email, "password": "correct horse battery"},
        headers=_csrf_headers(client),
    )
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct horse battery"},
        headers=_csrf_headers(client),
    )
    assert response.status_code == 200
    return response.json["data"]["csrf_token"]


def _add_category(app, name="Food"):
    with app.app_context():
        category = Category(category_name=name)
        db.session.add(category)
        db.session.commit()
        return category.category_id


def _preview(client, token, content, filename="transactions.csv"):
    return client.post(
        "/api/expenses/import/preview",
        data={"file": (BytesIO(content), filename)},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )


def _confirm(client, token, rows):
    return client.post(
        "/api/expenses/import/confirm",
        json={"rows": rows},
        headers={"X-CSRF-Token": token},
    )


def _approved_row(**overrides):
    row = {
        "date": "2026-08-01",
        "amount": "450.00",
        "category": "Food",
        "description": "Groceries",
        "vendor": "Local Market",
        "allow_duplicate": False,
    }
    row.update(overrides)
    return row


def test_preview_validates_rows_and_does_not_save_anything(client, app):
    token = _authenticated(client)
    _add_category(app)
    csv_content = (
        b"date,amount,category,description,vendor\n"
        b"2026-08-01,450,Food,Groceries,Local Market\n"
        b"2026-02-30,180,Food,Breakfast,City Cafe\n"
        b"2026-08-05,120,Unknown,Bus pass,City Bus\n"
        b"2026-08-06,20,Food,,\n"
    )

    response = _preview(client, token, csv_content)

    assert response.status_code == 200
    result = response.json["data"]
    assert result["summary"] == {
        "rows_total": 4,
        "valid_rows": 2,
        "invalid_rows": 2,
        "duplicate_rows": 0,
        "total_amount": "470.00",
        "sample_transactions": [
            {
                "date": "2026-08-01",
                "amount": "450.00",
                "category": "Food",
                "description": "Groceries",
                "vendor": "Local Market",
            },
            {
                "date": "2026-08-06",
                "amount": "20.00",
                "category": "Food",
                "description": "",
                "vendor": "",
            },
        ],
    }
    assert "date" in result["rows"][1]["errors"]
    assert "does not exist" in result["rows"][2]["errors"]["category"]
    assert result["rows"][3]["errors"] == {}
    with app.app_context():
        assert Expense.query.count() == 0


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"date,amount\n2026-08-01,10\n", "Missing required"),
        (b"date,amount,category,merchant\n2026-08-01,10,Food,Shop\n", "Unsupported"),
        (b"date,amount,category\n", "no transaction rows"),
    ],
)
def test_preview_rejects_empty_unsupported_or_malformed_csv(client, content, message):
    token = _authenticated(client)
    response = _preview(client, token, content)

    assert response.status_code == 400
    assert message.casefold() in response.json["message"].casefold()


@pytest.mark.parametrize(
    ("date_value", "amount", "expected_error"),
    [
        ("not-a-date", "10.00", "date"),
        ("2026-08-01", "-1.00", "amount"),
        ("2026-08-01", "0", "amount"),
        ("2026-08-01", "100000000.00", "amount"),
        ("2026-08-01", "1.001", "amount"),
        ("2026-08-01", "", "amount"),
    ],
)
def test_preview_marks_invalid_dates_and_amounts(client, app, date_value, amount, expected_error):
    token = _authenticated(client)
    _add_category(app)
    response = _preview(
        client,
        token,
        f"date,amount,category\n{date_value},{amount},Food\n".encode(),
    )

    assert response.status_code == 200
    assert expected_error in response.json["data"]["rows"][0]["errors"]


def test_preview_marks_malformed_row_shape_invalid(client, app):
    token = _authenticated(client)
    _add_category(app)
    response = _preview(
        client,
        token,
        b"date,amount,category\n2026-08-01,10,Food,extra\n",
    )

    assert response.status_code == 200
    assert response.json["data"]["summary"]["invalid_rows"] == 1
    assert "columns" in response.json["data"]["rows"][0]["errors"]["row"]


def test_import_persists_only_approved_rows_for_authenticated_owner(client, app):
    token = _authenticated(client)
    category_id = _add_category(app)
    with app.app_context():
        owner_id = User.query.filter_by(email="import@example.com").one().user_id
        existing = Expense(
            user_id=owner_id,
            category_id=category_id,
            amount=Decimal("5.00"),
            date=date(2026, 7, 1),
            description="Existing expense",
            vendor="Existing vendor",
        )
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.expense_id

    preview = _preview(
        client,
        token,
        b"date,amount,category,description,vendor\n"
        b"2026-08-01,450,Food,Groceries,Local Market\n"
        b"2026-08-02,90,Food,Taxi,City Cab\n",
    )
    rows = [row["data"] for row in preview.json["data"]["rows"]]
    response = _confirm(client, token, rows)

    assert response.status_code == 201
    assert response.json["data"]["imported"] == 2
    with app.app_context():
        expenses = Expense.query.order_by(Expense.expense_id).all()
        assert len(expenses) == 3
        assert expenses[0].expense_id == existing_id
        assert expenses[0].description == "Existing expense"
        assert all(expense.user_id == owner_id for expense in expenses)
        assert expenses[1].category_id == category_id
        assert expenses[1].payment_method is None


def test_duplicate_preview_and_reimport_are_safe_and_can_be_explicitly_approved(client, app):
    token = _authenticated(client)
    category_id = _add_category(app)
    first_preview = _preview(
        client,
        token,
        b"date,amount,category,description,vendor\n"
        b"2026-08-01,450,Food,Groceries,Local Market\n"
        b"2026-08-01,450,Food,Groceries,Local Market\n"
        b"2026-08-01,450,Food,Bus fare,City Bus\n",
    )
    first_rows = first_preview.json["data"]["rows"]
    assert first_rows[0]["potential_duplicate"] is False
    assert first_rows[1]["potential_duplicate"] is True
    assert first_rows[1]["duplicate_of"] == {"type": "row", "row_number": 2}
    assert first_rows[2]["potential_duplicate"] is False
    assert first_preview.json["data"]["summary"]["duplicate_rows"] == 1

    initial_import = _confirm(
        client,
        token,
        [{**first_rows[0]["data"], "allow_duplicate": False}],
    )
    assert initial_import.status_code == 201
    reimport_preview = _preview(
        client,
        token,
        b"date,amount,category,description,vendor\n"
        b"2026-08-01,450,Food,Groceries,Local Market\n",
    )
    assert reimport_preview.json["data"]["rows"][0]["potential_duplicate"] is True

    blocked = _confirm(
        client,
        token,
        [{**reimport_preview.json["data"]["rows"][0]["data"], "allow_duplicate": False}],
    )
    assert blocked.status_code == 409
    assert blocked.json["data"]["duplicates"][0]["duplicate_of"]["type"] == "expense"
    with app.app_context():
        assert Expense.query.filter_by(category_id=category_id).count() == 1

    allowed = _confirm(
        client,
        token,
        [{**reimport_preview.json["data"]["rows"][0]["data"], "allow_duplicate": True}],
    )
    assert allowed.status_code == 201


def test_import_endpoint_requires_authentication_and_rejects_user_id_injection(client, app):
    unauthenticated = _preview(client, "", b"date,amount,category\n2026-08-01,10,Food\n")
    assert unauthenticated.status_code == 401

    token = _authenticated(client)
    _add_category(app)
    response = _confirm(client, token, [{**_approved_row(), "user_id": 999}])
    assert response.status_code == 400
    with app.app_context():
        assert Expense.query.count() == 0


@pytest.mark.parametrize(
    ("filename", "content", "status", "message"),
    [
        pytest.param("transactions.txt", b"date,amount,category\n2026-08-01,10,Food\n", 400, ".csv", id="wrong-extension"),
        pytest.param("transactions.csv", b"\xff\xfe", 400, "UTF-8", id="invalid-encoding"),
        pytest.param("transactions.csv", b"x" * (MAX_CSV_BYTES + 1), 413, "5 MB", id="file-too-large"),
    ],
)
def test_preview_rejects_invalid_file_type_encoding_and_size(client, filename, content, status, message):
    token = _authenticated(client)
    response = _preview(client, token, content, filename)
    assert response.status_code == status
    assert message.casefold() in response.json["message"].casefold()


def test_preview_rejects_more_than_the_row_limit(client):
    token = _authenticated(client)
    content = b"date,amount,category\n" + b"2026-08-01,10,Food\n" * (MAX_CSV_ROWS + 1)

    response = _preview(client, token, content)

    assert response.status_code == 413
    assert str(MAX_CSV_ROWS) in response.json["message"]


def test_database_failure_rolls_back_the_entire_import(client, app, monkeypatch):
    token = _authenticated(client)
    _add_category(app)
    original_commit = Session.commit

    def fail_when_importing(self):
        if any(isinstance(item, Expense) for item in self.new):
            raise SQLAlchemyError("injected database failure")
        return original_commit(self)

    monkeypatch.setattr(Session, "commit", fail_when_importing)
    response = _confirm(client, token, [
        _approved_row(),
        _approved_row(date="2026-08-02", description="Dinner", vendor="Cafe"),
    ])

    assert response.status_code == 503
    assert "No rows were saved" in response.json["message"]
    with app.app_context():
        assert Expense.query.count() == 0
