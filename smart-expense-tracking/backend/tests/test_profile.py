from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app import create_app
from extensions import db
from models import User


class TestConfig:
    TESTING = True
    SECRET_KEY = "profile-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ["http://localhost:5173"]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    ADMIN_EMAILS = set()
    PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024
    MAX_CONTENT_LENGTH = PROFILE_PHOTO_MAX_BYTES + 256 * 1024


@pytest.fixture
def app(tmp_path):
    test_app = create_app(TestConfig)
    test_app.config["PROFILE_UPLOAD_DIR"] = str(tmp_path / "profile-photos")
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_headers(client):
    token_response = client.get("/api/auth/csrf")
    return {"X-CSRF-Token": token_response.json["data"]["csrf_token"]}


def register_and_login(client, email):
    client.post(
        "/api/auth/register",
        json={"name": "Profile User", "email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct horse battery"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    return response.json["data"]["csrf_token"]


def make_image(format_name="PNG"):
    content = BytesIO()
    Image.new("RGB", (8, 8), color="purple").save(content, format=format_name)
    content.seek(0)
    return content


def test_profile_requires_authentication_for_all_account_routes(client):
    assert client.get("/api/users/profile").status_code == 401
    assert client.put("/api/users/profile", json={"name": "New"}).status_code == 401
    assert client.post("/api/users/profile/photo").status_code == 401
    assert client.get("/api/users/profile/photo").status_code == 401
    assert client.delete("/api/users/profile/photo").status_code == 401
    assert client.post("/api/users/password", json={}).status_code == 401


def test_get_and_update_profile_and_current_user(client, app):
    csrf_token = register_and_login(client, "profile-one@example.com")
    initial = client.get("/api/users/profile")
    assert initial.status_code == 200
    assert initial.json["data"]["user"]["username"] is None
    assert initial.json["data"]["user"]["profile_photo_url"] is None
    assert initial.json["data"]["user"]["created_at"]

    response = client.put(
        "/api/users/profile",
        json={
            "name": "Updated Profile",
            "username": "updated.user",
            "date_of_birth": "2000-03-12",
            "phone_number": "+1 555 010 2020",
            "gender": "Prefer not to say",
            "bio": "I track my personal finances.",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    user = response.json["data"]["user"]
    assert user["name"] == "Updated Profile"
    assert user["username"] == "updated.user"
    assert user["date_of_birth"] == "2000-03-12"
    assert user["bio"] == "I track my personal finances."
    assert client.get("/api/auth/me").json["data"]["user"]["username"] == "updated.user"
    with app.app_context():
        assert User.query.filter_by(email="profile-one@example.com").one().date_of_birth == date(2000, 3, 12)


def test_profile_validates_fields_and_preserves_data_when_invalid(client):
    csrf_token = register_and_login(client, "profile-invalid@example.com")
    response = client.put(
        "/api/users/profile",
        json={"name": "", "username": "x", "date_of_birth": "2999-01-01", "bio": "ok"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 400
    assert set(response.json["errors"]) >= {"name", "username", "date_of_birth"}
    assert client.get("/api/users/profile").json["data"]["user"]["name"] == "Profile User"
    assert client.put(
        "/api/users/profile", json={"user_id": 999, "name": "Someone else"},
        headers={"X-CSRF-Token": csrf_token},
    ).status_code == 400


def test_username_and_email_uniqueness_and_email_reauthentication(client):
    first_token = register_and_login(client, "first-profile@example.com")
    assert client.put(
        "/api/users/profile", json={"username": "same.name"},
        headers={"X-CSRF-Token": first_token},
    ).status_code == 200

    register_and_login(client, "second-profile@example.com")
    second_token = csrf_headers(client)["X-CSRF-Token"]
    conflict = client.put(
        "/api/users/profile", json={"username": "SAME.NAME"},
        headers={"X-CSRF-Token": second_token},
    )
    assert conflict.status_code == 400
    assert "username" in conflict.json["errors"]
    missing_reauth = client.put(
        "/api/users/profile", json={"email": "changed@example.com"},
        headers={"X-CSRF-Token": second_token},
    )
    assert missing_reauth.status_code == 400
    duplicate_email = client.put(
        "/api/users/profile",
        json={"email": "first-profile@example.com", "current_password": "correct horse battery"},
        headers={"X-CSRF-Token": second_token},
    )
    assert duplicate_email.status_code == 400
    assert "email" in duplicate_email.json["errors"]
    changed = client.put(
        "/api/users/profile",
        json={"email": "changed@example.com", "current_password": "correct horse battery"},
        headers={"X-CSRF-Token": second_token},
    )
    assert changed.status_code == 200


def test_profile_photo_upload_replace_remove_and_missing_file(client, app):
    csrf_token = register_and_login(client, "photo-profile@example.com")
    uploaded = client.post(
        "/api/users/profile/photo",
        data={"photo": (make_image(), "../../untrusted.png")},
        headers={"X-CSRF-Token": csrf_token},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 200
    photo_url = uploaded.json["data"]["user"]["profile_photo_url"]
    filename = photo_url.split("v=")[1]
    stored_path = Path(app.config["PROFILE_UPLOAD_DIR"]) / filename
    assert filename != "../../untrusted.png"
    assert stored_path.is_file()
    image_response = client.get(photo_url)
    assert image_response.status_code == 200
    assert image_response.mimetype == "image/png"
    assert image_response.headers["Cache-Control"] == "private, no-store"
    assert image_response.headers["X-Content-Type-Options"] == "nosniff"

    second_upload = client.post(
        "/api/users/profile/photo",
        data={"photo": (make_image("WEBP"), "replace.webp")},
        headers={"X-CSRF-Token": csrf_token},
        content_type="multipart/form-data",
    )
    assert second_upload.status_code == 200
    assert second_upload.json["data"]["user"]["profile_photo_url"].endswith(".webp")

    new_filename = second_upload.json["data"]["user"]["profile_photo_url"].split("v=")[1]
    photo_path = Path(app.config["PROFILE_UPLOAD_DIR"]) / new_filename
    photo_path.unlink()
    assert client.get(second_upload.json["data"]["user"]["profile_photo_url"]).status_code == 404
    removed = client.delete("/api/users/profile/photo", headers={"X-CSRF-Token": csrf_token})
    assert removed.status_code == 200
    assert removed.json["data"]["user"]["profile_photo_url"] is None
    assert client.get("/api/users/profile/photo").status_code == 404
    assert not stored_path.exists()


@pytest.mark.parametrize(
    ("content", "filename", "status"),
    [
        (b"not an image", "bad.exe", 400),
        (None, "too-large.png", 413),
    ],
)
def test_profile_photo_rejects_invalid_type_and_oversized_upload(client, app, content, filename, status):
    csrf_token = register_and_login(client, f"reject-{status}@example.com")
    if content is None:
        content = b"x" * (app.config["PROFILE_PHOTO_MAX_BYTES"] + 1)
    response = client.post(
        "/api/users/profile/photo",
        data={"photo": (BytesIO(content), filename)},
        headers={"X-CSRF-Token": csrf_token},
        content_type="multipart/form-data",
    )
    assert response.status_code == status


def test_photo_is_only_available_to_authenticated_owner(client):
    first_token = register_and_login(client, "photo-owner@example.com")
    uploaded = client.post(
        "/api/users/profile/photo",
        data={"photo": (make_image(), "owner.png")},
        headers={"X-CSRF-Token": first_token},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 200
    protected_url = uploaded.json["data"]["user"]["profile_photo_url"]

    client.post("/api/auth/logout", headers={"X-CSRF-Token": first_token})
    assert client.get(protected_url).status_code == 401
    register_and_login(client, "other-photo-user@example.com")
    assert client.get("/api/users/profile/photo").status_code == 404
    assert client.get(protected_url).status_code == 404


def test_password_change_reauthenticates_and_updates_hash(client, app):
    csrf_token = register_and_login(client, "password-profile@example.com")
    assert client.post(
        "/api/users/password",
        json={"current_password": "wrong", "new_password": "brand new password"},
        headers={"X-CSRF-Token": csrf_token},
    ).status_code == 400
    assert client.post(
        "/api/users/password",
        json={"current_password": "correct horse battery", "new_password": "short"},
        headers={"X-CSRF-Token": csrf_token},
    ).status_code == 400
    changed = client.post(
        "/api/users/password",
        json={"current_password": "correct horse battery", "new_password": "brand new password"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert changed.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="password-profile@example.com").one()
        assert user.check_password("brand new password")
        assert not user.check_password("correct horse battery")


def test_profile_migration_command_is_repeatable(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["migrate-profile"]).exit_code == 0
    assert runner.invoke(args=["migrate-profile"]).exit_code == 0
