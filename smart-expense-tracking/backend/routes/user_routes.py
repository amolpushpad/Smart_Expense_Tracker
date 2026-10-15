import io
import re
import uuid
from datetime import date
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file, session
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import User
from services.auth_service import validate_email

user_bp = Blueprint("users", __name__)
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
PHONE_PATTERN = re.compile(r"^[+()\d .-]{7,30}$")
PHOTO_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
PHOTO_MIME_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
EDITABLE_FIELDS = {"name", "username", "date_of_birth", "phone_number", "gender", "bio", "email", "current_password"}


def _current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def _photo_directory():
    configured_directory = current_app.config.get("PROFILE_UPLOAD_DIR")
    directory = Path(configured_directory) if configured_directory else Path(current_app.instance_path) / "profile_photos"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _photo_path(filename):
    if not filename or Path(filename).name != filename or not re.fullmatch(r"[0-9a-f]{32}\.(jpg|png|webp)", filename):
        return None
    return _photo_directory() / filename


@user_bp.get("/profile")
def get_profile():
    user = _current_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    return jsonify(success=True, data={"user": user.to_safe_dict()})


@user_bp.put("/profile")
def update_profile():
    user = _current_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(success=False, message="A JSON object is required."), 400
    errors = {}
    changes = {}
    unknown_fields = set(payload) - EDITABLE_FIELDS
    if unknown_fields:
        return jsonify(success=False, message="Unsupported profile fields were supplied."), 400

    if "name" in payload:
        name = payload["name"].strip() if isinstance(payload["name"], str) else ""
        if not name or len(name) > 120:
            errors["name"] = "Name must be between 1 and 120 characters."
        else:
            changes["name"] = name

    if "username" in payload:
        raw_username = payload["username"]
        username = raw_username.strip() if isinstance(raw_username, str) else ""
        if raw_username not in ("", None) and not isinstance(raw_username, str):
            errors["username"] = "Username must be text."
        elif username and not USERNAME_PATTERN.fullmatch(username):
            errors["username"] = "Username must be 3–30 characters using letters, numbers, dots, underscores, or hyphens."
        else:
            username = username.lower() if username else None
        if not errors.get("username") and username and User.query.filter(
            User.username == username, User.user_id != user.user_id
        ).first():
            errors["username"] = "That username is already in use."
        elif not errors.get("username"):
            changes["username"] = username

    if "email" in payload:
        email = payload["email"].strip().lower() if isinstance(payload["email"], str) else ""
        if not validate_email(email):
            errors["email"] = "Enter a valid email address."
        elif email != user.email and (
            not isinstance(payload.get("current_password"), str)
            or not user.check_password(payload["current_password"])
        ):
            errors["current_password"] = "Enter your current password to change your email."
        elif User.query.filter(User.email == email, User.user_id != user.user_id).first():
            errors["email"] = "An account with this email already exists."
        else:
            changes["email"] = email

    if "date_of_birth" in payload:
        value = payload["date_of_birth"]
        if value in ("", None):
            changes["date_of_birth"] = None
        elif not isinstance(value, str):
            errors["date_of_birth"] = "Enter a valid date of birth."
        else:
            try:
                parsed_date = date.fromisoformat(value)
                if parsed_date > date.today():
                    raise ValueError
                changes["date_of_birth"] = parsed_date
            except ValueError:
                errors["date_of_birth"] = "Enter a valid date of birth that is not in the future."

    if "phone_number" in payload:
        raw_phone = payload["phone_number"]
        phone = raw_phone.strip() if isinstance(raw_phone, str) else ""
        if raw_phone not in ("", None) and not isinstance(raw_phone, str):
            errors["phone_number"] = "Enter a valid phone number."
        elif phone and not PHONE_PATTERN.fullmatch(phone):
            errors["phone_number"] = "Enter a valid phone number."
        else:
            changes["phone_number"] = phone or None

    for field, limit in (("gender", 40), ("bio", 500)):
        if field in payload:
            raw_value = payload[field]
            value = raw_value.strip() if isinstance(raw_value, str) else ""
            if raw_value not in ("", None) and not isinstance(raw_value, str):
                errors[field] = f"{field.replace('_', ' ').capitalize()} must be text."
            elif len(value) > limit:
                errors[field] = f"{field.replace('_', ' ').capitalize()} must be {limit} characters or fewer."
            else:
                changes[field] = value or None

    if not any(field in payload for field in EDITABLE_FIELDS - {"current_password"}):
        errors["profile"] = "Provide at least one profile field to update."
    if errors:
        return jsonify(success=False, message="Please correct the highlighted fields.", errors=errors), 400

    try:
        for field, value in changes.items():
            setattr(user, field, value)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="That username or email is already in use."), 409
    return jsonify(success=True, message="Profile updated.", data={"user": user.to_safe_dict()})


@user_bp.post("/profile/photo")
def upload_profile_photo():
    user = _current_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    uploaded = request.files.get("photo")
    if uploaded is None or not uploaded.filename:
        return jsonify(success=False, message="Choose an image to upload."), 400

    photo_bytes = uploaded.stream.read(current_app.config["PROFILE_PHOTO_MAX_BYTES"] + 1)
    if len(photo_bytes) > current_app.config["PROFILE_PHOTO_MAX_BYTES"]:
        return jsonify(success=False, message="Profile photos must be 5 MB or smaller."), 413
    try:
        with Image.open(io.BytesIO(photo_bytes)) as image:
            image_format = image.format
            image.verify()
        if image_format not in PHOTO_FORMATS:
            raise ValueError("Unsupported image format.")
        with Image.open(io.BytesIO(photo_bytes)) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Image dimensions are too large.")
            image.load()
            if image_format == "JPEG":
                image = image.convert("RGB")
            elif image_format == "PNG":
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            else:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            extension = PHOTO_FORMATS[image_format][0]
            filename = f"{uuid.uuid4().hex}.{extension}"
            target = _photo_directory() / filename
            image.save(target, format=image_format, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return jsonify(success=False, message="Upload a valid JPEG, PNG, or WebP image no larger than 20 megapixels."), 400

    old_filename = user.profile_photo
    user.profile_photo = filename
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        target.unlink(missing_ok=True)
        raise
    old_path = _photo_path(old_filename)
    if old_path and old_path != target:
        old_path.unlink(missing_ok=True)
    return jsonify(success=True, message="Profile photo updated.", data={"user": user.to_safe_dict()}), 200


@user_bp.get("/profile/photo")
def get_profile_photo():
    user = _current_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    path = _photo_path(user.profile_photo)
    if not path:
        return jsonify(success=False, message="No profile photo is available."), 404
    try:
        photo_content = path.read_bytes()
    except FileNotFoundError:
        return jsonify(success=False, message="No profile photo is available."), 404
    response = send_file(io.BytesIO(photo_content), mimetype=PHOTO_MIME_TYPES[path.suffix[1:]])
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@user_bp.delete("/profile/photo")
def delete_profile_photo():
    user = _current_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    old_path = _photo_path(user.profile_photo)
    user.profile_photo = None
    db.session.commit()
    if old_path:
        old_path.unlink(missing_ok=True)
    return jsonify(success=True, message="Profile photo removed.", data={"user": user.to_safe_dict()})


@user_bp.post("/password")
def change_password():
    user = _current_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"current_password", "new_password"}:
        return jsonify(success=False, message="Current and new passwords are required."), 400
    current_password = payload["current_password"]
    new_password = payload["new_password"]
    if not isinstance(current_password, str) or not user.check_password(current_password):
        return jsonify(success=False, message="Current password is incorrect."), 400
    if not isinstance(new_password, str) or not 8 <= len(new_password) <= 128:
        return jsonify(success=False, message="New password must be between 8 and 128 characters."), 400
    if user.check_password(new_password):
        return jsonify(success=False, message="Choose a new password different from your current password."), 400
    user.set_password(new_password)
    db.session.commit()
    return jsonify(success=True, message="Password changed successfully.")
