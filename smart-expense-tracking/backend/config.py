import os
import secrets
from urllib.parse import quote_plus


def _database_uri():
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = quote_plus(os.getenv("MYSQL_USER", "smart_expense_user"))
    password = quote_plus(os.getenv("MYSQL_PASSWORD", ""))
    database = quote_plus(os.getenv("MYSQL_DATABASE", "smart_expense_tracking"))
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ]
    ADMIN_EMAILS = {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }
    PROFILE_UPLOAD_DIR = os.getenv("PROFILE_UPLOAD_DIR") or None
    PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024
    MAX_CONTENT_LENGTH = PROFILE_PHOTO_MAX_BYTES + 256 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
