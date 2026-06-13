"""
QuickSell v3 - Rotas: Carrinho e Checkout
"""
from __future__ import annotations

from flask import (Blueprint, render_template, redirect, url_for,
                   request, jsonify, flash, session, abort)
from ..extensions import db
from ..models import Store, Product, Order, OrderItem, OrderStatus
from ..utils.cart import (add_to_cart, remove_from_cart, update_cart_qty,
                           clear_cart, cart_summary)

cart_bp = Blueprint("cart", __name__)


def _get_active_store(slug: str) -> Store:
    store = Store.query.filter_by(slug=slug, is_active=True).first()
    if not store:
        abort(404)
    return store


# ── Adicionar ao carrinho ─────────────────────────────────────────────────────

@cart_bp.route("/store/<slug>/cart/add", methods=["POST"])
def add(slug):
    store      = _get_active_store(slug)
    product_id = request.form.get("product_id", type=int)
    qty        = request.form.get("qty", 1, type=int)
    is_ajax    = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    product = Product.query.filter_by(
        id=product_id, store_id=store.id, is_active=True
    ).first()

    if not product:
        if is_ajax:
            return jsonify({"ok": False, "error": "Produto não encontrado"}), 404
        flash("Produto não encontrado.", "error")
        return redirect(url_for("store_public.view_store", slug=slug))

    if product.effective_stock == 0:
        if is_ajax:
            return jsonify({"ok": False, "error": "Produto sem estoque"}), 400
        flash("Produto esgotado.", "error")
        return redirect(url_for("store_public.view_store", slug=slug))

    add_to_cart(slug, product, qty)
    summary = cart_summary(slug)

    if is_ajax:
        return jsonify({
            "ok":          True,
            "item_count":  summary.item_count,
            "cart_total":  f"{summary.total:.2f}",
            "product_name": product.name,
        })

    flash(f'"{product.name}" adicionado ao carrinho!', "success")
    return redirect(url_for("store_public.view_store", slug=slug))


# ── Ver carrinho ──────────────────────────────────────────────────────────────

@cart_bp.route("/store/<slug>/cart")
def view(slug):
    store   = _get_active_store(slug)
    summary = cart_summary(slug)
    return render_template("store/cart.html", store=store, summary=summary)


# ── Remover item ──────────────────────────────────────────────────────────────

@cart_bp.route("/store/<slug>/cart/remove", methods=["POST"])
def remove(slug):
    _get_active_store(slug)
    product_id = request.form.get("product_id", type=int)
    remove_from_cart(slug, product_id)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        s = cart_summary(slug)
        return jsonify({
            "ok":       True,
            "item_count": s.item_count,
            "subtotal":   s.subtotal,
            "shipping":   s.shipping,
            "total":      s.total,
        })

    return redirect(url_for("cart.view", slug=slug))


# ── Atualizar quantidade ──────────────────────────────────────────────────────

@cart_bp.route("/store/<slug>/cart/update", methods=["POST"])
def update(slug):
    store      = _get_active_store(slug)
    product_id = request.form.get("product_id", type=int)
    qty        = request.form.get("qty", type=int)

    product = Product.query.filter_by(id=product_id, store_id=store.id).first()
    if product and qty is not None:
        update_cart_qty(slug, product, qty)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        s = cart_summary(slug)
        return jsonify({
            "ok":         True,
            "item_count": s.item_count,
            "subtotal":   s.subtotal,
            "shipping":   s.shipping,
            "total":      s.total,
        })

    return redirect(url_for("cart.view", slug=slug))


# ── Checkout GET ──────────────────────────────────────────────────────────────

@cart_bp.route("/store/<slug>/checkout")
def checkout(slug):
    store   = _get_active_store(slug)
    summary = cart_summary(slug)

    if not summary.items:
        flash("Seu carrinho está vazio.", "info")
        return redirect(url_for("store_public.view_store", slug=slug))

    return render_template("store/checkout.html", store=store, summary=summary)


# ── Checkout POST → criar pedido ──────────────────────────────────────────────

@cart_bp.route("/store/<slug>/checkout", methods=["POST"])
def checkout_submit(slug):
    store   = _get_active_store(slug)
    summary = cart_summary(slug)

    if not summary.items:
        flash("Seu carrinho está vazio.", "info")
        return redirect(url_for("store_public.view_store", slug=slug))

    # Validar campos obrigatórios
    required = {
        "customer_name":  "Nome completo",
        "customer_email": "E-mail",
        "customer_phone": "Telefone",
        "address_zip":    "CEP",
        "address_street": "Endereço",
        "address_number": "Número",
        "address_city":   "Cidade",
        "address_state":  "Estado",
    }
    data   = {field: request.form.get(field, "").strip() for field in required}
    errors = [f"{label} é obrigatório." for field, label in required.items() if not data[field]]

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("store/checkout.html", store=store,
                               summary=summary, form_data=data)

    # Verificar estoque (concorrência)
    stock_errors = []
    for item in summary.items:
        product = Product.query.get(item.product_id)
        if not product or not product.is_active:
            stock_errors.append(f'"{item.name}" não está mais disponível.')
        elif product.effective_stock < item.qty:
            stock_errors.append(
                f'"{item.name}": apenas {product.effective_stock} unidade(s) em estoque.'
            )

    if stock_errors:
        for e in stock_errors:
            flash(e, "error")
        return render_template("store/checkout.html", store=store,
                               summary=summary, form_data=data)

    # Criar pedido
    order = Order(
        store_id  = store.id,
        status    = OrderStatus.PENDING,
        subtotal  = summary.subtotal,
        shipping  = summary.shipping,
        total     = summary.total,
        **data,
    )
    db.session.add(order)
    db.session.flush()

    # Criar itens e decrementar estoque
    for item in summary.items:
        product = Product.query.get(item.product_id)
        product.decrement_stock(item.qty)
        db.session.add(OrderItem(
            order_id     = order.id,
            product_id   = item.product_id,
            product_name = item.name,
            quantity     = item.qty,
            price        = item.price,
        ))

    db.session.commit()

    clear_cart(slug)

    # Se a loja tem Mercado Pago configurado, redireciona para PIX
    from ..models import MercadoPagoConfig
    mp_cfg = MercadoPagoConfig.query.filter_by(store_id=store.id, is_active=True).first()
    if mp_cfg and mp_cfg.access_token:
        return redirect(url_for("payment.pix_page", slug=slug, order_id=order.id))

    # Sem MP: fluxo antigo (lojista combina pagamento manualmente)
    session[f"last_order_{slug}"] = order.id
    return redirect(url_for("cart.order_success", slug=slug, order_id=order.id))


# ── Confirmação ───────────────────────────────────────────────────────────────

@cart_bp.route("/store/<slug>/pedido/<int:order_id>/confirmacao")
def order_success(slug, order_id):
    store = _get_active_store(slug)

    if session.get(f"last_order_{slug}") != order_id:
        return redirect(url_for("store_public.view_store", slug=slug))

    order = Order.query.filter_by(id=order_id, store_id=store.id).first_or_404()
    return render_template("store/order_success.html", store=store, order=order)
