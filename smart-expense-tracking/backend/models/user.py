from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class User(db.Model):
    __tablename__ = "user"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    username = db.Column(db.String(30), unique=True, index=True)
    date_of_birth = db.Column(db.Date)
    phone_number = db.Column(db.String(30))
    gender = db.Column(db.String(40))
    bio = db.Column(db.String(500))
    profile_photo = db.Column(db.String(255))
    password_hash = db.Column("password", db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expenses = db.relationship("Expense", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_safe_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "phone_number": self.phone_number,
            "gender": self.gender,
            "bio": self.bio,
            "profile_photo_url": f"/api/users/profile/photo?v={self.profile_photo}" if self.profile_photo else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }