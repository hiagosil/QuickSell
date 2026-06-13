"""
QuickSell v4 - Servico Mercado Pago
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

MP_API_BASE             = "https://api.mercadopago.com"
PIX_EXPIRATION_MINUTES  = 30


class MPException(Exception):
    def __init__(self, message: str, status_code: int = 0, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response    = response or {}


class MercadoPagoService:
    """
    Cliente HTTP para a API do Mercado Pago.
    Instanciado por requisicao com o access_token do lojista (multi-tenant).
    """

    def __init__(self, access_token: str):
        if not access_token:
            raise MPException("access_token nao configurado para esta loja.")
        self.access_token = access_token
        self._session     = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        })

    def create_pix_payment(
        self,
        order_id: int,
        amount: float,
        customer_email: str,
        customer_name: str,
        description: str,
        idempotency_key: str,
        notification_url: str,
    ) -> dict:
        """
        Cria um pagamento PIX.
        Retorna o payload da API incluindo qr_code e qr_code_base64.
        """
        expires_at = datetime.utcnow() + timedelta(minutes=PIX_EXPIRATION_MINUTES)
        parts      = customer_name.strip().split(" ", 1)
        first      = parts[0]
        last       = parts[1] if len(parts) > 1 else first

        payload = {
            "transaction_amount": round(float(amount), 2),
            "description":        description[:255],
            "payment_method_id":  "pix",
            "date_of_expiration": expires_at.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "payer": {
                "email":      customer_email,
                "first_name": first,
                "last_name":  last,
            },
            "external_reference": str(order_id),
            "notification_url":   notification_url,
        }

        headers = {"X-Idempotency-Key": idempotency_key}
        resp    = self._session.post(
            f"{MP_API_BASE}/v1/payments",
            json=payload,
            headers=headers,
            timeout=15,
        )

        if resp.status_code not in (200, 201):
            logger.error("MP create_pix error %s: %s", resp.status_code, resp.text[:500])
            raise MPException(
                f"Erro ao criar PIX (HTTP {resp.status_code})",
                status_code=resp.status_code,
                response=resp.json() if resp.content else {},
            )

        return resp.json()

    def get_payment(self, mp_payment_id: str) -> dict:
        """Consulta status de um pagamento pelo ID do MP."""
        resp = self._session.get(
            f"{MP_API_BASE}/v1/payments/{mp_payment_id}",
            timeout=10,
        )
        if resp.status_code != 200:
            raise MPException(
                f"Erro ao consultar pagamento {mp_payment_id}: {resp.status_code}",
                status_code=resp.status_code,
            )
        return resp.json()

    @staticmethod
    def validate_webhook_signature(
        x_signature: str,
        x_request_id: str,
        data_id: str,
        webhook_secret: str,
    ) -> bool:
        """
        Valida assinatura HMAC-SHA256 do webhook.

        O MP envia: x-signature: ts=<ts>,v1=<hmac>
        Mensagem assinada: id:<data_id>;request-id:<req_id>;ts:<ts>;

        Ref: https://www.mercadopago.com.br/developers/pt/docs/
             your-integrations/notifications/webhooks
        """
        if not webhook_secret or not x_signature:
            return False

        try:
            parts = dict(p.split("=", 1) for p in x_signature.split(","))
            ts    = parts.get("ts", "")
            v1    = parts.get("v1", "")
            if not ts or not v1:
                return False
        except Exception:
            return False

        message  = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        expected = hmac.new(
            webhook_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, v1)

    @staticmethod
    def generate_idempotency_key(order_id: int) -> str:
        return f"qs-order-{order_id}-{uuid.uuid4().hex}"


def get_mp_service(store) -> Tuple[Optional[MercadoPagoService], Optional[str]]:
    """
    Factory: retorna (servico, None) ou (None, mensagem_erro).
    """
    cfg = getattr(store, "mp_config", None)
    if not cfg or not cfg.is_active or not cfg.access_token:
        return None, "Pagamento via PIX nao configurado para esta loja."
    try:
        return MercadoPagoService(cfg.access_token), None
    except MPException as e:
        return None, str(e)
