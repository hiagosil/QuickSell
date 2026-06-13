"""
QuickSell v3 - Modelos: Order e OrderItem
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List
from ..extensions import db


class OrderStatus:
    PENDING   = "pendente"
    PAID      = "pago"
    SHIPPED   = "enviado"
    DELIVERED = "entregue"
    CANCELLED = "cancelado"

    ALL = [PENDING, PAID, SHIPPED, DELIVERED, CANCELLED]

    LABELS = {
        PENDING:   "Pendente",
        PAID:      "Pago",
        SHIPPED:   "Enviado",
        DELIVERED: "Entregue",
        CANCELLED: "Cancelado",
    }

    COLORS = {
        PENDING:   "warning",
        PAID:      "info",
        SHIPPED:   "purple",
        DELIVERED: "success",
        CANCELLED: "danger",
    }

    TRANSITIONS = {
        PENDING:   [PAID, CANCELLED],
        PAID:      [SHIPPED, CANCELLED],
        SHIPPED:   [DELIVERED],
        DELIVERED: [],
        CANCELLED: [],
    }


class Order(db.Model):
    __tablename__ = "orders"

    id             = db.Column(db.Integer, primary_key=True)

    customer_name  = db.Column(db.String(200), nullable=False)
    customer_email = db.Column(db.String(200), nullable=False)
    customer_phone = db.Column(db.String(30),  nullable=True)

    address_zip    = db.Column(db.String(10),  nullable=True)
    address_street = db.Column(db.String(300), nullable=True)
    address_number = db.Column(db.String(20),  nullable=True)
    address_city   = db.Column(db.String(120), nullable=True)
    address_state  = db.Column(db.String(2),   nullable=True)

    subtotal       = db.Column(db.Numeric(10, 2), default=0)
    shipping       = db.Column(db.Numeric(10, 2), default=0)
    total          = db.Column(db.Numeric(10, 2), nullable=False)

    status         = db.Column(db.String(20), default=OrderStatus.PENDING, index=True)
    notes          = db.Column(db.Text, nullable=True)

    store_id       = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship(
        "OrderItem",
        backref="order",
        lazy=True,
        cascade="all, delete-orphan",
    )

    @property
    def status_label(self) -> str:
        return OrderStatus.LABELS.get(self.status, self.status.capitalize())

    @property
    def status_color(self) -> str:
        return OrderStatus.COLORS.get(self.status, "")

    @property
    def can_update_status(self) -> bool:
        return bool(OrderStatus.TRANSITIONS.get(self.status))

    @property
    def next_statuses(self) -> List[str]:          # List[str] compatível com Python 3.8+
        return OrderStatus.TRANSITIONS.get(self.status, [])

    @property
    def full_address(self) -> str:
        parts = []
        if self.address_street: parts.append(self.address_street)
        if self.address_number: parts.append(f"nº {self.address_number}")
        if self.address_city:   parts.append(self.address_city)
        if self.address_state:  parts.append(self.address_state)
        if self.address_zip:    parts.append(f"CEP {self.address_zip}")
        return ", ".join(parts) if parts else "Endereço não informado"

    def item_count(self) -> int:
        return sum(i.quantity for i in self.items)

    def __repr__(self) -> str:
        return f"<Order #{self.id} {self.customer_name!r} {self.status}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id           = db.Column(db.Integer, primary_key=True)
    order_id     = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id   = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    quantity     = db.Column(db.Integer, nullable=False, default=1)
    price        = db.Column(db.Numeric(10, 2), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)

    product = db.relationship("Product", backref="order_items", lazy=True)

    @property
    def subtotal(self) -> Decimal:
        return self.price * self.quantity

    def __repr__(self) -> str:
        return f"<OrderItem {self.product_name!r} x{self.quantity}>"
