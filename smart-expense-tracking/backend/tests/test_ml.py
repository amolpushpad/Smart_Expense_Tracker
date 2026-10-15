from datetime import date
import builtins

import pytest

from app import create_app
from extensions import db
from models import Category, Expense, Income, User
from services import categorization_service, prediction_service


class TestConfig:
    TESTING = True
    SECRET_KEY = "ml-test-secret"
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
        for name in ["Food", "Transportation", "Bills", "Shopping", "Entertainment", "Healthcare", "Education", "Other"]:
            db.session.add(Category(category_name=name))
        db.session.commit()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_headers(client):
    return {"X-CSRF-Token": client.get("/api/auth/csrf").json["data"]["csrf_token"]}


def register_and_login(client, email):
    client.post(
        "/api/auth/register",
        json={"name": "ML User", "email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    return response.json["data"]["csrf_token"]


def add_expense(app, email, category, amount, expense_date, description, vendor=None):
    with app.app_context():
        user = User.query.filter_by(email=email).one()
        category_record = Category.query.filter_by(category_name=category).one()
        record = Expense(
            user_id=user.user_id,
            category_id=category_record.category_id,
            amount=amount,
            date=expense_date,
            description=description,
            vendor=vendor,
        )
        db.session.add(record)
        db.session.commit()
        return record.expense_id


def test_categorization_keyword_examples_and_unknown_description(client):
    register_and_login(client, "categorize@example.com")
    examples = [
        ({"description": "Grocery store vegetables"}, "Food", "keyword_fallback"),
        ({"description": "Electricity bill"}, "Bills", "keyword_fallback"),
        ({"description": "Online electronics purchase"}, "Shopping", "keyword_fallback"),
        ({"description": "Taxi ride"}, "Transportation", "keyword_fallback"),
    ]
    for payload, category, method in examples:
        response = client.post("/api/ml/categorize", json=payload, headers=csrf_headers(client))
        assert response.status_code == 200
        assert response.json["data"]["suggested_category"] == category
        assert response.json["data"]["method"] == method
        assert response.json["data"]["explanation"]

    unknown = client.post(
        "/api/ml/categorize",
        json={"description": "qzxv blorf zzzz"},
        headers=csrf_headers(client),
    )
    assert unknown.status_code == 200
    assert unknown.json["data"]["method"] in {
        "tfidf_logistic_regression", "fallback_unavailable", "unavailable_category"
    }


def test_categorization_uses_model_when_available_and_never_saves_expense(client, app):
    register_and_login(client, "model-categorize@example.com")
    if categorization_service._text_classifier.cache_info().currsize == 0:
        pytest.importorskip("sklearn")
    response = client.post(
        "/api/ml/categorize",
        json={"description": "Brunch meal"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.json["data"]["suggested_category"] == "Food"
    assert response.json["data"]["method"] == "tfidf_logistic_regression"
    assert 0 <= response.json["data"]["confidence"] <= 1
    with app.app_context():
        assert Expense.query.count() == 0


def test_categorization_validates_auth_input_and_model_failure(client, monkeypatch):
    assert client.post("/api/ml/categorize", json={"description": "Dinner"}).status_code == 401
    register_and_login(client, "bad-categorize@example.com")
    assert client.post("/api/ml/categorize", json={"description": " "}, headers=csrf_headers(client)).status_code == 400
    assert client.post(
        "/api/ml/categorize",
        json={"description": "Dinner", "unsupported": True},
        headers=csrf_headers(client),
    ).status_code == 400

    monkeypatch.setattr("routes.ml_routes.suggest_category", lambda *_: (_ for _ in ()).throw(RuntimeError("injected failure")))
    response = client.post(
        "/api/ml/categorize",
        json={"description": "Unrecognized phrase"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 503
    assert response.json["success"] is False


def test_categorization_falls_back_cleanly_when_classifier_dependency_is_missing(app, monkeypatch):
    original_import = builtins.__import__

    def without_sklearn(name, *args, **kwargs):
        if name.startswith("sklearn"):
            raise ImportError("test-only missing sklearn")
        return original_import(name, *args, **kwargs)

    categorization_service._text_classifier.cache_clear()
    with app.app_context():
        monkeypatch.setattr(builtins, "__import__", without_sklearn)
        suggestion = categorization_service.suggest_category("A very unusual phrase")
    categorization_service._text_classifier.cache_clear()
    assert suggestion["method"] == "fallback_unavailable"
    assert suggestion["suggested_category"] is None


def test_prediction_reports_insufficient_history_without_a_fake_value(client):
    register_and_login(client, "insufficient-prediction@example.com")
    response = client.get("/api/ml/prediction?month=10&year=2026")
    assert response.status_code == 200
    prediction = response.json["data"]["prediction"]
    assert prediction["prediction_value"] is None
    assert prediction["sufficient_history"] is False
    assert "At least 3" in prediction["explanation"]


def test_prediction_with_sufficient_history_and_regression_or_baseline(app, client):
    register_and_login(client, "prediction-history@example.com")
    for month in range(1, 9):
        add_expense(
            app,
            "prediction-history@example.com",
            "Food",
            f"{month * 10}.00",
            date(2026, month, 10),
            f"Month {month}",
        )
    response = client.get("/api/ml/prediction?month=10&year=2026")
    prediction = response.json["data"]["prediction"]

    assert response.status_code == 200
    assert prediction["sufficient_history"] is True
    assert prediction["history_months"] == 8
    assert prediction["prediction_value"] is not None
    assert prediction["model"] in {"historical_daily_average", "scikit_learn_linear_regression"}
    assert prediction["currency"] == "INR"
    assert prediction["is_estimate"] is True
    assert prediction["prediction_period"]["month"] == 10
    assert "not financial advice" in prediction["explanation"]


def test_prediction_uses_historical_average_when_sklearn_is_unavailable(app, client, monkeypatch):
    register_and_login(client, "average-prediction@example.com")
    for month in range(1, 5):
        add_expense(
            app,
            "average-prediction@example.com",
            "Food",
            f"{month * 20}.00",
            date(2026, month, 10),
            f"Month {month}",
        )
    with app.app_context():
        user_id = User.query.filter_by(email="average-prediction@example.com").one().user_id
        original_import = builtins.__import__

        def without_sklearn(name, *args, **kwargs):
            if name.startswith("sklearn"):
                raise ImportError("test-only missing sklearn")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", without_sklearn)
        prediction = prediction_service.predict_monthly_spending(
            user_id, 10, 2026, today=date(2026, 10, 12)
        )
    assert prediction["sufficient_history"] is True
    assert prediction["model"] == "historical_daily_average"
    assert prediction["prediction_value"] is not None


def test_anomaly_detector_flags_large_expense_only_after_category_history(app):
    register_and_login(app.test_client(), "anomaly@example.com")
    for day in range(1, 7):
        add_expense(app, "anomaly@example.com", "Food", "10.00", date(2026, 1, day), f"Meal {day}")
    unusual_id = add_expense(app, "anomaly@example.com", "Food", "250.00", date(2026, 1, 7), "Large meal")
    client = app.test_client()
    register_and_login(client, "anomaly@example.com")

    response = client.get("/api/ml/anomalies")
    assert response.status_code == 200
    anomalies = response.json["data"]["anomalies"]
    assert [item["expense_id"] for item in anomalies] == [unusual_id]
    assert anomalies[0]["detection_method"] == "category_median_mad"
    assert "unusual-spending" in anomalies[0]["reason"]


def test_anomaly_requires_five_prior_same_category_transactions(client, app):
    register_and_login(client, "few-anomalies@example.com")
    for day in range(1, 5):
        add_expense(app, "few-anomalies@example.com", "Food", "10.00", date(2026, 1, day), f"Meal {day}")
    add_expense(app, "few-anomalies@example.com", "Food", "1000.00", date(2026, 1, 5), "Few history")
    response = client.get("/api/ml/anomalies")
    assert response.status_code == 200
    assert response.json["data"]["anomalies"] == []


def test_duplicate_matching_uses_date_amount_category_and_normalized_text(client, app):
    register_and_login(client, "duplicates@example.com")
    duplicate_one = add_expense(app, "duplicates@example.com", "Food", "15.00", date(2026, 2, 4), "Coffee and bagel", "Campus Cafe")
    duplicate_two = add_expense(app, "duplicates@example.com", "Food", "15.00", date(2026, 2, 4), " coffee, and bagel! ", " campus   cafe ")
    add_expense(app, "duplicates@example.com", "Food", "15.00", date(2026, 2, 4), "Different item", "Other vendor")
    add_expense(app, "duplicates@example.com", "Food", "15.00", date(2026, 2, 5), "Coffee and bagel", "Campus Cafe")

    response = client.get("/api/ml/duplicates")
    assert response.status_code == 200
    pairs = response.json["data"]["duplicates"]
    assert len(pairs) == 1
    assert pairs[0]["first"]["expense_id"] == duplicate_one
    assert pairs[0]["second"]["expense_id"] == duplicate_two
    assert "normalized description matches" in pairs[0]["matching_reasons"]


def test_ml_endpoints_are_user_scoped_and_insight_failure_is_isolated(client, app, monkeypatch):
    assert client.get("/api/ml/anomalies").status_code == 401
    assert client.get("/api/ml/duplicates").status_code == 401
    assert client.get("/api/ml/insights").status_code == 401
    register_and_login(client, "ml-owner@example.com")
    add_expense(app, "ml-owner@example.com", "Food", "100.00", date(2026, 2, 1), "Owner transaction")
    other = app.test_client()
    register_and_login(other, "ml-other@example.com")

    report = other.get("/api/ml/anomalies")
    duplicates = other.get("/api/ml/duplicates")
    assert report.status_code == duplicates.status_code == 200
    assert report.json["data"]["anomalies"] == []
    assert duplicates.json["data"]["duplicates"] == []
    assert other.get("/api/ml/insights?month=2&year=2026").json["data"]["prediction"]["history_months"] == 0

    monkeypatch.setattr(
        "routes.ml_routes.detect_unusual_expenses",
        lambda *_: (_ for _ in ()).throw(RuntimeError("injected detector failure")),
    )
    insights = other.get("/api/ml/insights?month=2&year=2026")
    assert insights.status_code == 200
    assert "anomalies" in insights.json["data"]["errors"]
    assert "prediction" in insights.json["data"]
    assert "duplicates" in insights.json["data"]


def test_ml_date_parameters_are_validated(client):
    register_and_login(client, "invalid-ml@example.com")
    assert client.get("/api/ml/prediction?month=13&year=2026").status_code == 400
    assert client.get("/api/ml/insights?month=1&year=not-a-year").status_code == 400
    assert client.get("/api/ml/prediction?month=2&year=1899").status_code == 400
