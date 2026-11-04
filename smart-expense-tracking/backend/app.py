"""Application entry point and app factory for the expense tracker API."""
import secrets
from decimal import Decimal
from pathlib import Path

import click
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
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    from models import Category
    from routes.auth_routes import auth_bp
    from routes.analytics_routes import analytics_bp
    from routes.budget_routes import budget_bp
    from routes.category_routes import category_bp
    from routes.corporate_routes import corporate_bp
    from routes.corporate_workflow_routes import corporate_workflow_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.demo_routes import demo_bp
    from routes.expense_routes import expense_bp
    from routes.expense_import_routes import expense_import_bp
    from routes.income_routes import income_bp
    from routes.ml_routes import ml_bp
    from routes.user_routes import user_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(budget_bp, url_prefix="/api/budgets")
    app.register_blueprint(category_bp, url_prefix="/api/categories")
    app.register_blueprint(corporate_bp, url_prefix="/api/corporate")
    app.register_blueprint(corporate_workflow_bp, url_prefix="/api/corporate")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(demo_bp, url_prefix="/api/demo")
    app.register_blueprint(expense_bp, url_prefix="/api/expenses")
    app.register_blueprint(expense_import_bp, url_prefix="/api/expenses")
    app.register_blueprint(income_bp, url_prefix="/api/income")
    app.register_blueprint(ml_bp, url_prefix="/api/ml")
    app.register_blueprint(user_bp, url_prefix="/api/users")

    @app.before_request
    def enforce_csrf():
        csrf_paths = {
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/logout",
            "/api/corporate/organizations",
            "/api/corporate/join",
        }
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

    @app.cli.command("migrate-corporate-workflows")
    def migrate_corporate_workflows():
        """Add corporate workflow fields and history tables without changing personal data."""
        db.create_all()
        additions = {
            "corporate_organizations": {
                "organization_email": "VARCHAR(254) NULL",
                "contact_phone": "VARCHAR(30) NULL",
                "address": "VARCHAR(300) NULL",
                "status": "VARCHAR(20) NOT NULL DEFAULT 'active'",
                "joining_enabled": "BOOLEAN NOT NULL DEFAULT 1",
            },
            "corporate_departments": {
                "manager_id": "INTEGER NULL",
                "status": "VARCHAR(20) NOT NULL DEFAULT 'active'",
            },
            "corporate_memberships": {
                "membership_status": "VARCHAR(20) NOT NULL DEFAULT 'active'",
                "joined_at": "DATETIME NULL",
            },
            "corporate_expenses": {
                "rejection_reason": "VARCHAR(500) NULL",
                "receipt_path": "VARCHAR(255) NULL",
                "receipt_filename": "VARCHAR(255) NULL",
                "paid_at": "DATETIME NULL",
                "updated_at": "DATETIME NULL",
            },
        }
        preparer = db.engine.dialect.identifier_preparer
        with db.engine.begin() as connection:
            for table_name, columns in additions.items():
                existing = {column["name"] for column in inspect(connection).get_columns(table_name)}
                for column_name, definition in columns.items():
                    if column_name in existing:
                        continue
                    quoted_table = preparer.quote(table_name)
                    quoted_column = preparer.quote(column_name)
                    connection.execute(text(
                        f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {definition}"
                    ))
        db.create_all()
        print("Corporate workflow fields and history tables are ready; existing records were preserved.")

    @app.cli.command("import-synthetic-snapshots")
    @click.option("--csv", "csv_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
    @click.option("--usd-inr-rate", type=click.FloatRange(min=0.0001), default=95, show_default=True)
    def import_synthetic_snapshots(csv_path, usd_inr_rate):
        """Import synthetic profile snapshots into their isolated table, converting USD to INR."""
        from sqlalchemy.exc import SQLAlchemyError

        from ml.import_synthetic_snapshots import import_snapshot_csv

        try:
            result = import_snapshot_csv(csv_path, usd_inr_rate)
        except (ValueError, SQLAlchemyError) as error:
            raise ClickException(str(error)) from error
        if result["already_imported"]:
            print(f"Dataset already imported ({result['records']} snapshots at ₹{result['rate']}/USD); no rows changed.")
        else:
            print(f"Imported {result['imported']} isolated synthetic snapshots at ₹{result['rate']}/USD.")

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

    @app.cli.command("seed-corporate-demo")
    def seed_corporate_demo():
        """Create an isolated fictional organization and three months of corporate expenses."""
        from datetime import date

        from models import CorporateExpense, CorporateMembership, Department, Organization, User

        organization_name = "Northstar Demo Corporation"
        if Organization.query.filter_by(name=organization_name).first():
            print("The Northstar demo organization already exists; no data was changed.")
            return

        demo_accounts = [
            ("Alex Morgan", "admin@northstar-demo.example", "Admin"),
            ("Jordan Lee", "employee@northstar-demo.example", "Employee"),
            ("Riley Chen", "manager@northstar-demo.example", "Manager"),
            ("Taylor Brooks", "finance@northstar-demo.example", "Finance Officer"),
            ("Casey Patel", "executive@northstar-demo.example", "Executive"),
        ]
        if any(User.query.filter_by(email=email).first() for _, email, _ in demo_accounts):
            raise ClickException("A Northstar demo email already exists. No data was changed; choose another demo database.")

        organization = Organization(name=organization_name)
        db.session.add(organization)
        db.session.flush()
        department_names = ("Engineering", "Sales", "Operations")
        departments = {
            name: Department(organization_id=organization.organization_id, name=name)
            for name in department_names
        }
        db.session.add_all(departments.values())
        db.session.flush()

        users = {}
        role_departments = {
            "Admin": "Operations",
            "Employee": "Engineering",
            "Manager": "Engineering",
            "Finance Officer": "Operations",
            "Executive": "Sales",
        }
        for name, email, role in demo_accounts:
            user = User(name=name, email=email)
            user.set_password("NorthstarDemo2026!")
            db.session.add(user)
            db.session.flush()
            users[role] = user
            db.session.add(CorporateMembership(
                organization_id=organization.organization_id,
                user_id=user.user_id,
                department_id=departments[role_departments[role]].department_id,
                role=role,
            ))

        today = date.today()
        month_dates = []
        for months_back in (2, 1, 0):
            month_index = today.year * 12 + today.month - 1 - months_back
            year, month_zero = divmod(month_index, 12)
            month = month_zero + 1
            month_dates.append(date(year, month, min(today.day, 28)))
        records = [
            (0, "Employee", "Travel", "City Transit", "Client-site commute", "Pending Manager"),
            (0, "Employee", "Meals", "Harvest Cafe", "Project planning lunch", "Pending Finance"),
            (0, "Manager", "Software", "CloudDesk", "Team collaboration license", "Approved"),
            (1, "Employee", "Equipment", "ByteWorks", "Development peripherals", "Approved"),
            (1, "Employee", "Travel", "MetroRail", "Customer workshop", "Rejected"),
            (1, "Manager", "Training", "LearnHub", "Team certification course", "Approved"),
            (2, "Employee", "Travel", "Northstar Air", "Quarterly customer visit", "Pending Manager"),
            (2, "Employee", "Office Supplies", "Paper & Co", "Team stationery", "Approved"),
            (2, "Manager", "Software", "DataCloud", "Analytics subscription", "Pending Finance"),
        ]
        for month_offset, submitter_role, category, merchant, description, status in records:
            submitter = users[submitter_role]
            row = CorporateExpense(
                organization_id=organization.organization_id,
                submitter_id=submitter.user_id,
                department_id=departments[role_departments[submitter_role]].department_id,
                amount=Decimal("125.00") + Decimal(month_offset * 47),
                expense_date=month_dates[month_offset],
                category=category,
                merchant=merchant,
                description=description,
                status=status,
                manager_id=users["Manager"].user_id if status != "Pending Manager" else None,
                finance_id=users["Finance Officer"].user_id if status in ("Approved", "Rejected") else None,
            )
            db.session.add(row)
        db.session.commit()
        print(f"Created the fictional {organization_name} organization with data from three months.")
        print(f"Joining code: {organization.joining_code}")
        print("Demo password for all sample users: NorthstarDemo2026!")

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
