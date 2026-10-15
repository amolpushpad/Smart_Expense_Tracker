"""Application entry point and app factory for the expense tracker API."""
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from flask import Flask, jsonify, request, session
from click import ClickException
from flask_cors import CORS
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from config import Config
from extensions import db

def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    db.init_app(app)
    CORS(
        app,
        origins=app.config["CORS_ORIGINS"],
        supports_credentials=True,
        allow_headers=["Content-Type", "X-CSRF-Token"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    from models import Category
    from routes.auth_routes import auth_bp
    from routes.analytics_routes import analytics_bp
    from routes.budget_routes import budget_bp
    from routes.category_routes import category_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.expense_routes import expense_bp
    from routes.income_routes import income_bp
    from routes.ml_routes import ml_bp
    from routes.user_routes import user_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(budget_bp, url_prefix="/api/budgets")
    app.register_blueprint(category_bp, url_prefix="/api/categories")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(expense_bp, url_prefix="/api/expenses")
    app.register_blueprint(income_bp, url_prefix="/api/income")
    app.register_blueprint(ml_bp, url_prefix="/api/ml")
    app.register_blueprint(user_bp, url_prefix="/api/users")

    @app.before_request
    def enforce_csrf():
        csrf_paths = {"/api/auth/register", "/api/auth/login", "/api/auth/logout"}
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.path.startswith("/api/")
            and (request.path in csrf_paths or session.get("user_id"))
        ):
            expected = session.get("csrf_token", "")
            supplied = request.headers.get("X-CSRF-Token", "")
            if not expected or not secrets.compare_digest(expected, supplied):
                return jsonify(success=False, message="Your session token is missing or expired. Refresh and try again."), 400

    @app.get("/api/health")
    def health():
        db.session.execute(text("SELECT 1"))
        return jsonify(success=True, message="API and database are available.")

    @app.cli.command("init-db")
    def init_db():
        """Create core tables and seed predefined categories."""
        db.create_all()
        for name in ["Food", "Transportation", "Shopping", "Bills", "Entertainment", "Healthcare", "Education", "Other"]:
            if not Category.query.filter_by(category_name=name).first():
                db.session.add(Category(category_name=name))
        db.session.commit()
        print("Database tables are ready and default categories are seeded.")

    @app.cli.command("migrate-profile")
    def migrate_profile():
        """Add optional profile fields to an existing user table."""
        from models import User

        table_name = User.__tablename__
        if table_name not in inspect(db.engine).get_table_names():
            raise ClickException("Initialize the database first with `flask --app app init-db`.")
        columns = {
            "username": "VARCHAR(30)",
            "date_of_birth": "DATE",
            "phone_number": "VARCHAR(30)",
            "gender": "VARCHAR(40)",
            "bio": "VARCHAR(500)",
            "profile_photo": "VARCHAR(255)",
        }
        inspector = inspect(db.engine)
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        preparer = db.engine.dialect.identifier_preparer
        quoted_table = preparer.quote(table_name)
        with db.engine.begin() as connection:
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    quoted_column = preparer.quote(column_name)
                    connection.execute(text(
                        f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {column_type} NULL"
                    ))
            current_indexes = {index["name"] for index in inspect(connection).get_indexes(table_name)}
            index_name = "ix_user_username"
            if index_name not in current_indexes:
                quoted_index = preparer.quote(index_name)
                quoted_username = preparer.quote("username")
                connection.execute(text(
                    f"CREATE UNIQUE INDEX {quoted_index} ON {quoted_table} ({quoted_username})"
                ))
        print("Profile columns and username uniqueness are ready.")

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(_error):
        db.session.rollback()
        return jsonify(success=False, message="The database is unavailable or the request could not be saved."), 503

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify(success=False, message=error.description), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(_error):
        db.session.rollback()
        return jsonify(success=False, message="An unexpected server error occurred."), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
