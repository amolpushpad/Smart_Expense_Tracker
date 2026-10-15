from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Category
from models import User

category_bp = Blueprint("categories", __name__)


def _authenticated_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def _is_admin(user):
    return user.email.lower() in current_app.config["ADMIN_EMAILS"]


def _category_name(payload):
    name = payload.get("category_name") if isinstance(payload, dict) else None
    name = name.strip() if isinstance(name, str) else ""
    return name if name and len(name) <= 80 else None


@category_bp.get("")
def list_categories():
    if not _authenticated_user():
        return jsonify(success=False, message="Authentication required."), 401
    categories = Category.query.order_by(Category.category_name.asc()).all()
    return jsonify(success=True, data={"categories": [category.to_dict() for category in categories]})


@category_bp.post("")
def create_category():
    user = _authenticated_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    if not _is_admin(user):
        return jsonify(success=False, message="Administrator access required."), 403
    name = _category_name(request.get_json(silent=True))
    if not name:
        return jsonify(success=False, message="Category name must be between 1 and 80 characters."), 400
    category = Category(category_name=name)
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="That category already exists."), 409
    return jsonify(success=True, message="Category created.", data={"category": category.to_dict()}), 201


@category_bp.put("/<int:category_id>")
def update_category(category_id):
    user = _authenticated_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    if not _is_admin(user):
        return jsonify(success=False, message="Administrator access required."), 403
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify(success=False, message="Category not found."), 404
    name = _category_name(request.get_json(silent=True))
    if not name:
        return jsonify(success=False, message="Category name must be between 1 and 80 characters."), 400
    category.category_name = name
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, message="That category already exists."), 409
    return jsonify(success=True, message="Category updated.", data={"category": category.to_dict()})


@category_bp.delete("/<int:category_id>")
def delete_category(category_id):
    user = _authenticated_user()
    if not user:
        return jsonify(success=False, message="Authentication required."), 401
    if not _is_admin(user):
        return jsonify(success=False, message="Administrator access required."), 403
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify(success=False, message="Category not found."), 404
    if category.expenses:
        return jsonify(success=False, message="This category is in use and cannot be deleted."), 409
    db.session.delete(category)
    db.session.commit()
    return jsonify(success=True, message="Category deleted.")