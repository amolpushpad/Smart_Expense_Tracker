from extensions import db


class Category(db.Model):
    __tablename__ = "category"

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(80), nullable=False, unique=True)
    expenses = db.relationship("Expense", back_populates="category", passive_deletes=True)

    def to_dict(self):
        return {"category_id": self.category_id, "category_name": self.category_name}