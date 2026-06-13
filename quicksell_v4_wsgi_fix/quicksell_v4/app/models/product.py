"""
QuickSell - Modelo: Product (v3)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from ..extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text, nullable=True)
    price         = db.Column(db.Numeric(10, 2), nullable=False)

    # ── Estoque ──────────────────────────────
    stock          = db.Column(db.Integer, default=0)         # campo legado — mantido para compatibilidade
    stock_quantity = db.Column(db.Integer, default=0)         # campo principal v2+
    sku            = db.Column(db.String(100), nullable=True)

    # ── Imagem ───────────────────────────────
    image_url  = db.Column(db.String(500), nullable=True)     # URL externa
    image_path = db.Column(db.String(500), nullable=True)     # path de upload local

    # ── Categoria ────────────────────────────
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)

    # ── Propriedades ─────────────────────────

    @property
    def effective_stock(self) -> int:
        """Retorna stock_quantity se preenchido, senão stock (legado)."""
        return self.stock_quantity if self.stock_quantity is not None else (self.stock or 0)

    def is_in_stock(self) -> bool:
        return self.effective_stock > 0

    def decrement_stock(self, qty: int = 1) -> bool:
        """
        Decrementa o estoque após pedido.
        Retorna False se não houver estoque suficiente.
        """
        if self.effective_stock < qty:
            return False
        self.stock_quantity = self.effective_stock - qty
        self.stock = self.stock_quantity   # mantém legado sincronizado
        return True

    @property
    def image(self) -> Optional[str]:
        """
        Resolve a imagem do produto:
        1. Upload local (image_path) → /static/uploads/<filename>
        2. URL externa (image_url)
        3. None
        """
        if self.image_path:
            return f"/static/uploads/{self.image_path}"
        return self.image_url or None

    def __repr__(self) -> str:
        return f"<Product {self.name!r} R${self.price} estoque:{self.effective_stock}>"
