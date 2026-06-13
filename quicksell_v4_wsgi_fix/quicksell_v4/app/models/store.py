"""
QuickSell - Modelo: Store (v3)
"""
from datetime import datetime
from ..extensions import db

STORE_STYLES = ["minimalista", "dark", "neon"]


class Store(db.Model):
    __tablename__ = "stores"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(150), nullable=False)
    slug          = db.Column(db.String(150), unique=True, nullable=False, index=True)
    description   = db.Column(db.Text, nullable=True)
    category      = db.Column(db.String(80), nullable=True)
    logo_url      = db.Column(db.String(300), nullable=True)
    primary_color = db.Column(db.String(7), default="#3B82F6")
    style         = db.Column(db.String(20), default="minimalista")
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    products   = db.relationship("Product",  backref="store", lazy=True,
                                 cascade="all, delete-orphan", foreign_keys="Product.store_id")
    categories = db.relationship("Category", backref="store", lazy=True,
                                 cascade="all, delete-orphan", foreign_keys="Category.store_id")
    orders     = db.relationship("Order",    backref="store", lazy=True,
                                 cascade="all, delete-orphan", foreign_keys="Order.store_id")

    # ── Métodos de conveniência ──────────────────────────────────────────────

    def product_count(self) -> int:
        return len(self.products)

    def low_stock_count(self) -> int:
        return sum(1 for p in self.products if 0 < p.effective_stock <= 5)

    def out_of_stock_count(self) -> int:
        return sum(1 for p in self.products if p.effective_stock == 0)

    def pending_orders(self) -> int:
        # Import local — evita ciclo: store → order → (nada) mas mantém limpeza
        from .order import OrderStatus
        return sum(1 for o in self.orders if o.status == OrderStatus.PENDING)

    def total_revenue(self) -> float:
        from .order import OrderStatus
        paid = [o for o in self.orders
                if o.status not in (OrderStatus.PENDING, OrderStatus.CANCELLED)]
        return round(sum(float(o.total) for o in paid), 2)

    def __repr__(self) -> str:
        return f"<Store {self.name} ({self.slug})>"
