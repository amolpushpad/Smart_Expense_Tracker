from datetime import date

import pytest

from app import create_app
from extensions import db
from models import Category, Expense, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-only-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ["http://localhost:5173"]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    ADMIN_EMAILS = {"admin@example.com"}


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


def csrf_headers(client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["data"]["csrf_token"]}


def register(client, email="alex@example.com", **overrides):
    payload = {"name": "Alex Morgan", "email": email, "password": "correct horse battery"}
    payload.update(overrides)
    return client.post("/api/auth/register", json=payload, headers=csrf_headers(client))


def login(client, email="alex@example.com", password="correct horse battery"):
    headers = csrf_headers(client)
    response = client.post("/api/auth/login", json={"email": email, "password": password}, headers=headers)
    return response


def authenticated(client, email):
    assert register(client, email=email).status_code == 201
    response = login(client, email=email)
    assert response.status_code == 200
    return response.json["data"]["csrf_token"]


def add_category(app, name="Food"):
    with app.app_context():
        category = Category(category_name=name)
        db.session.add(category)
        db.session.commit()
        return category.category_id


def expense_payload(default_category_id, **overrides):
    payload = {
        "amount": "12.50",
        "date": "2026-02-12",
        "category_id": default_category_id,
        "description": "Lunch",
        "vendor": "Campus Cafe",
        "payment_method": "Card",
    }
    payload.update(overrides)
    return payload


def post_expense(client, csrf_token, payload):
    return client.post("/api/expenses", json=payload, headers={"X-CSRF-Token": csrf_token})


def test_successful_registration_stores_hash_and_returns_safe_user(client, app):
    response = register(client)

    assert response.status_code == 201
    assert response.json["success"] is True
    assert response.json["data"]["user"]["email"] == "alex@example.com"
    assert "password" not in response.json["data"]["user"]
    assert "password_hash" not in response.json["data"]["user"]
    with app.app_context():
        user = User.query.filter_by(email="alex@example.com").one()
        assert user.password_hash != "correct horse battery"
        assert user.check_password("correct horse battery")


def test_duplicate_registration_returns_conflict(client):
    assert register(client).status_code == 201
    response = register(client, email="ALEX@example.com")

    assert response.status_code == 409
    assert "email" in response.json["errors"]


@pytest.mark.parametrize(
    ("name", "email", "password"),
    [("", "alex@example.com", "long enough password"), ("Alex", "bad-email", "long enough password"), ("Alex", "alex@example.com", "short")],
)
def test_invalid_registration_is_rejected(client, name, email, password):
    response = register(client, name=name, email=email, password=password)

    assert response.status_code == 400
    assert response.json["success"] is False


def test_successful_login_sets_http_only_session_and_current_user(client):
    register(client)
    response = login(client)

    assert response.status_code == 200
    assert response.json["data"]["user"]["email"] == "alex@example.com"
    assert response.json["data"]["csrf_token"]
    assert "password" not in response.json["data"]["user"]
    assert "HttpOnly" in response.headers["Set-Cookie"]
    current = client.get("/api/auth/me")
    assert current.status_code == 200
    assert current.json["data"]["user"]["email"] == "alex@example.com"


def test_invalid_credentials_return_401(client):
    register(client)
    response = login(client, password="not the password")

    assert response.status_code == 401
    assert response.json["message"] == "Invalid email or password."


def test_current_user_requires_a_valid_session(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json["success"] is False


def test_logout_ends_session(client):
    register(client)
    logged_in = login(client)
    csrf_token = logged_in.json["data"]["csrf_token"]
    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})

    assert response.status_code == 200
    assert response.json["data"]["csrf_token"]
    assert client.get("/api/auth/me").status_code == 401


def test_profile_update_requires_authentication(client):
    response = client.put("/api/users/profile", json={"name": "Updated Name"})

    assert response.status_code == 401


def test_authenticated_user_can_update_profile(client):
    register(client)
    logged_in = login(client)
    response = client.put(
        "/api/users/profile",
        json={
            "name": "Alex Rivera",
            "email": "alex.rivera@example.com",
            "current_password": "correct horse battery",
        },
        headers={"X-CSRF-Token": logged_in.json["data"]["csrf_token"]},
    )

    assert response.status_code == 200
    assert response.json["data"]["user"]["name"] == "Alex Rivera"
    assert response.json["data"]["user"]["email"] == "alex.rivera@example.com"


def test_category_seed_command_is_idempotent(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["init-db"]).exit_code == 0
    assert runner.invoke(args=["init-db"]).exit_code == 0
    with app.app_context():
        assert Category.query.count() == 8


def test_expense_create_and_retrieve(client, app):
    csrf_token = authenticated(client, "alex@example.com")
    category_id = add_category(app)
    created = post_expense(client, csrf_token, expense_payload(category_id))

    assert created.status_code == 201
    expense_id = created.json["data"]["expense"]["expense_id"]
    assert created.json["data"]["expense"]["amount"] == "12.50"
    assert created.json["data"]["expense"]["category_name"] == "Food"
    assert client.get(f"/api/expenses/{expense_id}").status_code == 200


def test_expense_can_be_updated(client, app):
    csrf_token = authenticated(client, "alex@example.com")
    category_id = add_category(app)
    created = post_expense(client, csrf_token, expense_payload(category_id))
    expense_id = created.json["data"]["expense"]["expense_id"]
    updated = client.put(
        f"/api/expenses/{expense_id}",
        json={"amount": "20.00", "description": "Updated lunch"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert updated.status_code == 200
    assert updated.json["data"]["expense"]["amount"] == "20.00"
    assert updated.json["data"]["expense"]["description"] == "Updated lunch"


def test_expense_can_be_deleted(client, app):
    csrf_token = authenticated(client, "alex@example.com")
    category_id = add_category(app)
    created = post_expense(client, csrf_token, expense_payload(category_id))
    expense_id = created.json["data"]["expense"]["expense_id"]

    response = client.delete(f"/api/expenses/{expense_id}", headers={"X-CSRF-Token": csrf_token})

    assert response.status_code == 200
    assert client.get(f"/api/expenses/{expense_id}").status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "0"},
        {"amount": "-1.00"},
        {"amount": "1.001"},
        {"date": "not-a-date"},
        {"category_id": 9999},
    ],
)
def test_invalid_expense_values_are_rejected(client, app, overrides):
    csrf_token = authenticated(client, "alex@example.com")
    category_id = add_category(app)

    response = post_expense(client, csrf_token, expense_payload(category_id, **overrides))

    assert response.status_code == 400
    assert response.json["errors"]


def test_expense_list_search_and_filters(client, app):
    csrf_token = authenticated(client, "alex@example.com")
    food_id = add_category(app, "Food")
    transit_id = add_category(app, "Transportation")
    assert post_expense(client, csrf_token, expense_payload(food_id, date="2026-01-10", amount="10.00")).status_code == 201
    assert post_expense(
        client,
        csrf_token,
        expense_payload(transit_id, date="2026-01-20", amount="25.00", description="Train fare", vendor="Metro"),
    ).status_code == 201
    response = client.get(
        f"/api/expenses?category_id={transit_id}&start_date=2026-01-01&end_date=2026-01-31&min_amount=20&search=metro&sort=amount_high"
    )

    assert response.status_code == 200
    assert response.json["data"]["pagination"]["total"] == 1
    assert response.json["data"]["expenses"][0]["vendor"] == "Metro"
    assert response.json["data"]["total_amount"] == "25.00"


def test_expense_list_rejects_invalid_filter_parameters(client):
    authenticated(client, "alex@example.com")

    response = client.get("/api/expenses?start_date=2026-02-31&sort=invalid&page=0")

    assert response.status_code == 400
    assert {"start_date", "sort", "page"}.issubset(response.json["errors"])


def test_expense_list_sorts_and_paginates(client, app):
    csrf_token = authenticated(client, "alex@example.com")
    category_id = add_category(app)
    for amount, expense_date in [("10.00", "2026-01-01"), ("30.00", "2026-01-03"), ("20.00", "2026-01-02")]:
        assert post_expense(
            client,
            csrf_token,
            expense_payload(category_id, amount=amount, date=expense_date),
        ).status_code == 201

    highest = client.get("/api/expenses?sort=amount_high&per_page=2&page=1")
    next_page = client.get("/api/expenses?sort=oldest&per_page=2&page=2")

    assert [row["amount"] for row in highest.json["data"]["expenses"]] == ["30.00", "20.00"]
    assert highest.json["data"]["pagination"]["pages"] == 2
    assert [row["date"] for row in next_page.json["data"]["expenses"]] == ["2026-01-03"]


def test_user_cannot_access_another_users_expense(client, app):
    owner_token = authenticated(client, "alex@example.com")
    category_id = add_category(app)
    created = post_expense(client, owner_token, expense_payload(category_id))
    expense_id = created.json["data"]["expense"]["expense_id"]
    other_client = app.test_client()
    other_token = authenticated(other_client, "casey@example.com")

    assert other_client.get(f"/api/expenses/{expense_id}").status_code == 404
    assert other_client.put(
        f"/api/expenses/{expense_id}",
        json={"description": "Stolen edit"},
        headers={"X-CSRF-Token": other_token},
    ).status_code == 404
    assert other_client.delete(
        f"/api/expenses/{expense_id}", headers={"X-CSRF-Token": other_token}
    ).status_code == 404


def test_expense_list_requires_authentication(client):
    assert client.get("/api/expenses").status_code == 401
    response = client.post("/api/expenses", json={"amount": "12.50", "date": "2026-02-12", "category_id": 1})
    assert response.status_code == 401


def test_categories_are_readable_by_users_but_mutations_require_admin(client):
    user_token = authenticated(client, "alex@example.com")
    assert client.get("/api/categories").status_code == 200
    denied = client.post(
        "/api/categories",
        json={"category_name": "New category"},
        headers={"X-CSRF-Token": user_token},
    )
    assert denied.status_code == 403


def test_category_admin_crud_and_reference_delete_guard(client, app):
    admin_token = authenticated(client, "admin@example.com")
    created = client.post(
        "/api/categories",
        json={"category_name": "Special"},
        headers={"X-CSRF-Token": admin_token},
    )
    category_id = created.json["data"]["category"]["category_id"]
    assert created.status_code == 201
    updated = client.put(
        f"/api/categories/{category_id}",
        json={"category_name": "Special Updated"},
        headers={"X-CSRF-Token": admin_token},
    )
    assert updated.status_code == 200
    with app.app_context():
        expense = Expense(
            user_id=User.query.filter_by(email="admin@example.com").one().user_id,
            category_id=category_id,
            amount="3.25",
            date=date(2026, 2, 12),
        )
        db.session.add(expense)
        db.session.commit()
    blocked_delete = client.delete(f"/api/categories/{category_id}", headers={"X-CSRF-Token": admin_token})
    assert blocked_delete.status_code == 409
    assert client.delete("/api/categories/9999", headers={"X-CSRF-Token": admin_token}).status_code == 404