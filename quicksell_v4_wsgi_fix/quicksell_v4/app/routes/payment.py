"""
QuickSell v4 - Rotas: Pagamento PIX + Webhook Mercado Pago
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from flask import (Blueprint, render_template, redirect, url_for,
                   request, jsonify, flash, abort, current_app)
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Store, Order, OrderStatus, Payment, MercadoPagoConfig, PaymentStatus
from ..services.mercadopago import MercadoPagoService, MPException, get_mp_service

logger    = logging.getLogger(__name__)
payment_bp = Blueprint("payment", __name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_active_store(slug: str) -> Store:
    store = Store.query.filter_by(slug=slug, is_active=True).first()
    if not store:
        abort(404)
    return store


def _get_owned_store(store_id: int) -> Store:
    store = Store.query.filter_by(id=store_id, user_id=current_user.id).first()
    if not store:
        abort(404)
    return store


# ── Gerar PIX (chamado logo após criar o pedido) ──────────────────────────────

@payment_bp.route("/store/<slug>/pedido/<int:order_id>/pagar")
def pix_page(slug, order_id):
    """
    Página de pagamento PIX.
    Se o pagamento ainda não foi gerado, cria um novo via API.
    Se já existe e está aprovado, redireciona para sucesso.
    """
    store = _get_active_store(slug)
    order = Order.query.filter_by(id=order_id, store_id=store.id).first_or_404()

    # Já pago — redirecionar
    if order.status == OrderStatus.PAID:
        return redirect(url_for("cart.order_success", slug=slug, order_id=order_id))

    # Verificar se já existe pagamento PIX pendente e não expirado
    payment = Payment.query.filter_by(
        order_id=order.id,
        status=PaymentStatus.PENDING,
    ).order_by(Payment.created_at.desc()).first()

    if payment and payment.pix_copy_paste and not payment.is_expired:
        # Reusa PIX existente
        return render_template("store/pix.html",
                               store=store, order=order, payment=payment)

    # Precisa gerar novo PIX
    svc, err = get_mp_service(store)
    if err:
        flash(f"PIX indisponível: {err}", "error")
        return redirect(url_for("store_public.view_store", slug=slug))

    idempotency_key = MercadoPagoService.generate_idempotency_key(order.id)
    webhook_url     = url_for("payment.webhook", slug=slug, _external=True)
    description     = f"Pedido #{order.id} — {store.name}"

    try:
        resp = svc.create_pix_payment(
            order_id         = order.id,
            amount           = float(order.total),
            customer_email   = order.customer_email,
            customer_name    = order.customer_name,
            description      = description,
            idempotency_key  = idempotency_key,
            notification_url = webhook_url,
        )
    except MPException as e:
        logger.error("Erro ao gerar PIX para order %s: %s", order.id, e)
        flash("Não foi possível gerar o PIX no momento. Tente novamente.", "error")
        return redirect(url_for("store_public.view_store", slug=slug))

    # Extrair dados do PIX da resposta
    pix_data    = resp.get("point_of_interaction", {}).get("transaction_data", {})
    qr_code_b64 = pix_data.get("qr_code_base64", "")
    copy_paste  = pix_data.get("qr_code", "")
    mp_id       = str(resp.get("id", ""))
    expires_at  = datetime.utcnow() + timedelta(minutes=30)

    # Salvar Payment no banco
    payment = Payment(
        order_id          = order.id,
        store_id          = store.id,
        mp_payment_id     = mp_id,
        mp_status         = resp.get("status"),
        mp_status_detail  = resp.get("status_detail"),
        pix_qr_code       = qr_code_b64,
        pix_copy_paste    = copy_paste,
        pix_expires_at    = expires_at,
        status            = PaymentStatus.PENDING,
        amount            = order.total,
        idempotency_key   = idempotency_key,
        webhook_validated = False,
    )
    db.session.add(payment)
    db.session.commit()

    return render_template("store/pix.html",
                           store=store, order=order, payment=payment)


# ── Polling de status (AJAX) ──────────────────────────────────────────────────

@payment_bp.route("/store/<slug>/pedido/<int:order_id>/status")
def payment_status(slug, order_id):
    """
    Endpoint de polling chamado pela página PIX a cada 5 segundos.
    Retorna JSON com o status atual do pagamento.
    """
    store   = _get_active_store(slug)
    order   = Order.query.filter_by(id=order_id, store_id=store.id).first_or_404()
    payment = Payment.query.filter_by(order_id=order.id)\
                           .order_by(Payment.created_at.desc()).first()

    if not payment:
        return jsonify({"status": "pendente", "approved": False})

    # Consulta ativa no MP se ainda pendente (fallback para webhook)
    if payment.status == PaymentStatus.PENDING and payment.mp_payment_id:
        svc, _ = get_mp_service(store)
        if svc:
            try:
                mp_data   = svc.get_payment(payment.mp_payment_id)
                mp_status = mp_data.get("status", "")
                new_st    = PaymentStatus.MP_MAP.get(mp_status, PaymentStatus.PENDING)

                if new_st != payment.status:
                    payment.status   = new_st
                    payment.mp_status = mp_status
                    if new_st == PaymentStatus.APPROVED:
                        _approve_order(order, payment)
                    db.session.commit()
            except MPException:
                pass   # silencia falha de consulta — webhook ainda pode chegar

    return jsonify({
        "status":   payment.status,
        "label":    payment.status_label,
        "approved": payment.is_approved,
        "expired":  payment.is_expired,
        "redirect": url_for("cart.order_success", slug=slug, order_id=order_id)
                    if payment.is_approved else None,
    })


# ── Webhook Mercado Pago ──────────────────────────────────────────────────────

@payment_bp.route("/store/<slug>/webhook/mercadopago", methods=["POST"])
def webhook(slug):
    """
    Recebe notificações do Mercado Pago.

    Segurança implementada:
    1. Valida assinatura HMAC-SHA256 (x-signature header)
    2. Verifica idempotência: ignora mp_payment_id já processado como APPROVED
    3. Verifica que o pedido pertence à loja correta (store_id)
    4. Responde 200 imediatamente para evitar retry storm do MP

    Ref: https://www.mercadopago.com.br/developers/pt/docs/
         your-integrations/notifications/webhooks
    """
    store = Store.query.filter_by(slug=slug, is_active=True).first()
    if not store:
        return jsonify({"ok": False}), 404

    # ── 1. Validar assinatura HMAC ─────────────────────────────────────────
    cfg = getattr(store, "mp_config", None)
    if cfg and cfg.webhook_secret:
        x_sig    = request.headers.get("x-signature", "")
        x_req_id = request.headers.get("x-request-id", "")
        body     = request.get_json(silent=True) or {}
        data_id  = str(body.get("data", {}).get("id", ""))

        sig_valid = MercadoPagoService.validate_webhook_signature(
            x_sig, x_req_id, data_id, cfg.webhook_secret
        )
        if not sig_valid:
            logger.warning("Webhook com assinatura inválida para loja %s", slug)
            # Retorna 200 para evitar reenvio — MP não deve ter a chave certa
            return jsonify({"ok": False, "reason": "invalid_signature"}), 200

    # ── 2. Parsear payload ─────────────────────────────────────────────────
    body   = request.get_json(silent=True) or {}
    action = body.get("action", "")
    data   = body.get("data", {})

    # Só processa notificações de pagamento aprovado/atualizado
    if action not in ("payment.created", "payment.updated"):
        return jsonify({"ok": True, "skipped": True}), 200

    mp_payment_id = str(data.get("id", ""))
    if not mp_payment_id:
        return jsonify({"ok": False, "reason": "no_payment_id"}), 200

    # ── 3. Buscar pagamento no banco ───────────────────────────────────────
    payment = Payment.query.filter_by(
        mp_payment_id=mp_payment_id,
        store_id=store.id,
    ).first()

    if not payment:
        # Tentar criar registro mínimo consultando o MP
        logger.info("Webhook: payment %s não encontrado no banco, consultando MP", mp_payment_id)
        svc, err = get_mp_service(store)
        if err:
            return jsonify({"ok": False, "reason": "mp_not_configured"}), 200

        try:
            mp_data = svc.get_payment(mp_payment_id)
        except MPException as e:
            logger.error("Webhook: falha ao consultar MP para %s: %s", mp_payment_id, e)
            return jsonify({"ok": False}), 200

        order_id = mp_data.get("external_reference")
        if not order_id:
            return jsonify({"ok": False, "reason": "no_external_reference"}), 200

        order = Order.query.filter_by(
            id=int(order_id), store_id=store.id
        ).first()
        if not order:
            return jsonify({"ok": False, "reason": "order_not_found"}), 200

        payment = Payment(
            order_id          = order.id,
            store_id          = store.id,
            mp_payment_id     = mp_payment_id,
            status            = PaymentStatus.PENDING,
            amount            = order.total,
            webhook_validated = True,
        )
        db.session.add(payment)

    # ── 4. Idempotência — já aprovado? ─────────────────────────────────────
    if payment.status == PaymentStatus.APPROVED:
        logger.info("Webhook idempotente: payment %s já aprovado", mp_payment_id)
        return jsonify({"ok": True, "idempotent": True}), 200

    # ── 5. Consultar status real no MP ─────────────────────────────────────
    svc, err = get_mp_service(store)
    if not svc:
        return jsonify({"ok": False, "reason": err}), 200

    try:
        mp_data   = svc.get_payment(mp_payment_id)
        mp_status = mp_data.get("status", "")
        new_st    = PaymentStatus.MP_MAP.get(mp_status, PaymentStatus.PENDING)
    except MPException as e:
        logger.error("Webhook: falha ao consultar status do MP: %s", e)
        return jsonify({"ok": False}), 200

    # ── 6. Atualizar Payment ───────────────────────────────────────────────
    payment.mp_status         = mp_status
    payment.mp_status_detail  = mp_data.get("status_detail", "")
    payment.status            = new_st
    payment.webhook_validated = True

    # ── 7. Aprovar pedido se pago ──────────────────────────────────────────
    order = payment.order
    if new_st == PaymentStatus.APPROVED and order.status == OrderStatus.PENDING:
        _approve_order(order, payment)
        logger.info("Pedido #%s aprovado via webhook MP payment %s", order.id, mp_payment_id)

    db.session.commit()
    return jsonify({"ok": True}), 200


# ── Helpers internos ──────────────────────────────────────────────────────────

def _approve_order(order: Order, payment: Payment) -> None:
    """
    Marca pedido como PAGO.
    NÃO decrementa estoque aqui — já foi decrementado no checkout.
    Apenas atualiza status do Order e do Payment.
    """
    order.status   = OrderStatus.PAID
    payment.status = PaymentStatus.APPROVED


# ── Dashboard: configurar Mercado Pago ───────────────────────────────────────

@payment_bp.route("/stores/<int:store_id>/settings/mercadopago",
                  methods=["GET", "POST"])
@login_required
def mp_settings(store_id):
    store = _get_owned_store(store_id)
    cfg   = MercadoPagoConfig.query.filter_by(store_id=store.id).first()

    if request.method == "POST":
        action = request.form.get("action", "save")

        if action == "delete" and cfg:
            db.session.delete(cfg)
            db.session.commit()
            flash("Configuração do Mercado Pago removida.", "info")
            return redirect(url_for("payment.mp_settings", store_id=store_id))

        access_token   = request.form.get("access_token", "").strip()
        webhook_secret = request.form.get("webhook_secret", "").strip()

        if not access_token:
            flash("Access Token é obrigatório.", "error")
            return render_template("dashboard/mp_settings.html",
                                   store=store, cfg=cfg)

        if cfg:
            cfg.access_token   = access_token
            cfg.webhook_secret = webhook_secret or cfg.webhook_secret
            cfg.is_active      = True
        else:
            cfg = MercadoPagoConfig(
                store_id       = store.id,
                access_token   = access_token,
                webhook_secret = webhook_secret,
                is_active      = True,
            )
            db.session.add(cfg)

        db.session.commit()
        flash("Configuração salva com sucesso!", "success")
        return redirect(url_for("payment.mp_settings", store_id=store_id))

    return render_template("dashboard/mp_settings.html", store=store, cfg=cfg)


# ── Dashboard: painel financeiro ──────────────────────────────────────────────

@payment_bp.route("/stores/<int:store_id>/financeiro")
@login_required
def financial_dashboard(store_id):
    store = _get_owned_store(store_id)

    # Buscar todos os pagamentos da loja
    all_payments = Payment.query.filter_by(store_id=store.id)\
                                .order_by(Payment.created_at.desc()).all()

    approved  = [p for p in all_payments if p.status == PaymentStatus.APPROVED]
    pending   = [p for p in all_payments if p.status == PaymentStatus.PENDING]
    rejected  = [p for p in all_payments if p.status in
                 (PaymentStatus.REJECTED, PaymentStatus.CANCELLED, PaymentStatus.EXPIRED)]

    revenue       = sum(float(p.amount) for p in approved)
    pending_total = sum(float(p.amount) for p in pending)

    # Receita por dia (últimos 30 dias) para o gráfico
    from collections import defaultdict
    import datetime as dt
    revenue_by_day = defaultdict(float)
    cutoff = dt.date.today() - dt.timedelta(days=29)
    for p in approved:
        day = p.created_at.date()
        if day >= cutoff:
            revenue_by_day[day.isoformat()] += float(p.amount)

    # Preencher dias sem receita
    chart_labels = []
    chart_data   = []
    for i in range(30):
        day = (cutoff + dt.timedelta(days=i)).isoformat()
        chart_labels.append(day[-5:])   # MM-DD
        chart_data.append(round(revenue_by_day.get(day, 0.0), 2))

    return render_template(
        "dashboard/financial.html",
        store=store,
        all_payments=all_payments[:50],
        approved=approved,
        pending=pending,
        rejected=rejected,
        revenue=revenue,
        pending_total=pending_total,
        chart_labels=chart_labels,
        chart_data=chart_data,
        PaymentStatus=PaymentStatus,
    )
