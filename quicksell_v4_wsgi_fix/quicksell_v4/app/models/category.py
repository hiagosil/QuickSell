"""
QuickSell - Modelo: Category
Representa uma categoria de produtos dentro de uma loja.

NOTA: slugify NÃO é importado aqui — seria um import circular:
  models/__init__ → category.py → utils/__init__ → cart.py → models/__init__
  A geração de slug fica exclusivamente nas camadas de rota (routes/category.py).
"""

from datetime import datetime
from ..extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    slug       = db.Column(db.String(120), nullable=False)
    store_id   = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento: uma categoria tem vários produtos
    products = db.relationship(
        "Product",
        backref="category",
        lazy=True,
        foreign_keys="Product.category_id",
    )

    __table_args__ = (
        db.UniqueConstraint("slug", "store_id", name="uq_category_slug_store"),
    )

    def product_count(self) -> int:
        return len(self.products)

    def __repr__(self):
        return f"<Category {self.name}>"
