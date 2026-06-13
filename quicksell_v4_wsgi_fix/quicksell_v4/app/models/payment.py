"""
QuickSell v4 - Modelos: MercadoPagoConfig, Payment

MercadoPagoConfig: armazena o access_token por loja (criptografado em produção).
Payment: rastreia cada tentativa de pagamento PIX, vinculada a um Order.
"""
from __future__ import annotations

from datetime import datetime
from ..extensions import db


class MercadoPagoConfig(db.Model):
    """
    Configuração do Mercado Pago por loja.
    Cada lojista cadastra seu próprio access_token — multi-tenant.
    """
    __tablename__ = "mp_configs"

    id           = db.Column(db.Integer, primary_key=True)
    store_id     = db.Column(db.Integer, db.ForeignKey("stores.id"),
                             nullable=False, unique=True)
    access_token = db.Column(db.String(512), nullable=False)
    # webhook_secret: chave gerada pelo MP para validar assinatura HMAC-SHA256
    webhook_secret = db.Column(db.String(256), nullable=True)
    is_active    = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow,
                             onupdate=datetime.utcnow)

    store = db.relationship("Store", backref=db.backref("mp_config", uselist=False))

    def masked_token(self) -> str:
        """Exibe token parcialmente mascarado no dashboard."""
        if not self.access_token:
            return ""
        t = self.access_token
        return t[:8] + "••••••••" + t[-4:]

    def __repr__(self) -> str:
        return f"<MPConfig store_id={self.store_id}>"


class PaymentStatus:
    PENDING   = "pendente"
    APPROVED  = "aprovado"
    REJECTED  = "rejeitado"
    CANCELLED = "cancelado"
    EXPIRED   = "expirado"
    REFUNDED  = "estornado"

    ALL = [PENDING, APPROVED, REJECTED, CANCELLED, EXPIRED, REFUNDED]

    LABELS = {
        PENDING:   "Aguardando pagamento",
        APPROVED:  "Aprovado",
        REJECTED:  "Recusado",
        CANCELLED: "Cancelado",
        EXPIRED:   "Expirado",
        REFUNDED:  "Estornado",
    }

    COLORS = {
        PENDING:   "warning",
        APPROVED:  "success",
        REJECTED:  "danger",
        CANCELLED: "danger",
        EXPIRED:   "danger",
        REFUNDED:  "info",
    }

    # Status do MP → status interno
    MP_MAP = {
        "pending":     PENDING,
        "approved":    APPROVED,
        "authorized":  APPROVED,
        "in_process":  PENDING,
        "rejected":    REJECTED,
        "cancelled":   CANCELLED,
        "refunded":    REFUNDED,
        "charged_back": REFUNDED,
    }


class Payment(db.Model):
    """
    Representa uma tentativa de pagamento PIX via Mercado Pago.

    Campos de segurança:
    - mp_payment_id: ID único no MP — usado para idempotência (evita duplicatas)
    - webhook_validated: flag que marca se o webhook foi validado com HMAC
    """
    __tablename__ = "payments"

    id              = db.Column(db.Integer, primary_key=True)
    order_id        = db.Column(db.Integer, db.ForeignKey("orders.id"),
                                nullable=False)
    store_id        = db.Column(db.Integer, db.ForeignKey("stores.id"),
                                nullable=False)

    # Dados do MP
    mp_payment_id   = db.Column(db.String(100), nullable=True, unique=True, index=True)
    mp_preference_id= db.Column(db.String(200), nullable=True)
    mp_status       = db.Column(db.String(50),  nullable=True)   # status bruto do MP
    mp_status_detail= db.Column(db.String(100), nullable=True)

    # PIX
    pix_qr_code     = db.Column(db.Text,        nullable=True)   # base64 do QR
    pix_copy_paste  = db.Column(db.Text,        nullable=True)   # string copia-e-cola
    pix_expires_at  = db.Column(db.DateTime,    nullable=True)

    # Status interno
    status          = db.Column(db.String(30),
                                default=PaymentStatus.PENDING, index=True)
    amount          = db.Column(db.Numeric(10, 2), nullable=False)

    # Segurança
    webhook_validated = db.Column(db.Boolean, default=False)
    idempotency_key   = db.Column(db.String(100), nullable=True, unique=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    order = db.relationship("Order",
                            backref=db.backref("payments", lazy=True))

    @property
    def status_label(self) -> str:
        return PaymentStatus.LABELS.get(self.status, self.status)

    @property
    def status_color(self) -> str:
        return PaymentStatus.COLORS.get(self.status, "")

    @property
    def is_approved(self) -> bool:
        return self.status == PaymentStatus.APPROVED

    @property
    def is_expired(self) -> bool:
        if self.pix_expires_at and self.status == PaymentStatus.PENDING:
            return datetime.utcnow() > self.pix_expires_at
        return False

    def __repr__(self) -> str:
        return f"<Payment #{self.id} order={self.order_id} {self.status}>"
