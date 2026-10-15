import secrets

from flask import Blueprint, jsonify, request, session

from extensions import db
from models import User
from services.auth_service import authenticate_user, register_user

auth_bp = Blueprint("auth", __name__)


def _json_body():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


@auth_bp.get("/csrf")
def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return jsonify(success=True, data={"csrf_token": token})


@auth_bp.post("/register")
def register():
    payload = _json_body()
    user, errors = register_user(payload.get("name"), payload.get("email"), payload.get("password"))
    if errors:
        status = 409 if "already exists" in errors.get("email", "") else 400
        message = "An account with this email already exists." if status == 409 else "Please correct the highlighted fields."
        return jsonify(success=False, message=message, errors=errors), status
    return jsonify(success=True, message="Account created. Sign in to continue.", data={"user": user.to_safe_dict()}), 201


@auth_bp.post("/login")
def login():
    payload = _json_body()
    email = payload.get("email")
    password = payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        return jsonify(success=False, message="Email and password are required."), 400
    if "remember" in payload and not isinstance(payload["remember"], bool):
        return jsonify(success=False, message="Remember me must be a boolean value."), 400
    user = authenticate_user(email, password)
    if not user:
        return jsonify(success=False, message="Invalid email or password."), 401
    session.clear()
    session["user_id"] = user.user_id
    session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = bool(payload.get("remember", False))
    return jsonify(success=True, message="Signed in successfully.", data={"user": user.to_safe_dict(), "csrf_token": session["csrf_token"]})


@auth_bp.post("/logout")
def logout():
    session.clear()
    session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(success=True, message="Signed out successfully.", data={"csrf_token": session["csrf_token"]})


@auth_bp.get("/me")
def current_user():
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    if not user:
        session.pop("user_id", None)
        return jsonify(success=False, message="Authentication required."), 401
    return jsonify(success=True, data={"user": user.to_safe_dict()})