import re

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import User

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_email(email):
    return isinstance(email, str) and len(email) <= 254 and bool(EMAIL_PATTERN.fullmatch(email))


def register_user(name, email, password):
    errors = {}
    name = name.strip() if isinstance(name, str) else ""
    email = email.strip().lower() if isinstance(email, str) else ""

    if not name or len(name) > 120:
        errors["name"] = "Name must be between 1 and 120 characters."
    if not validate_email(email):
        errors["email"] = "Enter a valid email address."
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        errors["password"] = "Password must be between 8 and 128 characters."
    if errors:
        return None, errors
    if User.query.filter_by(email=email).first():
        return None, {"email": "An account with this email already exists."}

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, {"email": "An account with this email already exists."}
    return user, None


def authenticate_user(email, password):
    if not isinstance(email, str) or not isinstance(password, str):
        return None
    user = User.query.filter_by(email=email.strip().lower()).first()
    return user if user and user.check_password(password) else None