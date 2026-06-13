"""
QuickSell v3 - Rotas: Painel de Pedidos (lojista)
"""

from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, abort, jsonify)
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Store, Order, OrderItem, OrderStatus

orders_bp = Blueprint("orders", __name__)


def _get_owned_store(store_id: int) -> Store:
    store = Store.query.filter_by(id=store_id, user_id=current_user.id).first()
    if not store:
        abort(404)
    return store


# ── Lista de pedidos ──────────────────────────────────────────────────────────

@orders_bp.route("/stores/<int:store_id>/orders")
@login_required
def list_orders(store_id):
    store  = _get_owned_store(store_id)
    status = request.args.get("status", "")
    q      = Order.query.filter_by(store_id=store.id)
    if status and status in OrderStatus.ALL:
        q = q.filter_by(status=status)
    orders = q.order_by(Order.created_at.desc()).all()

    counts = {s: Order.query.filter_by(store_id=store.id, status=s).count()
              for s in OrderStatus.ALL}
    counts["all"] = Order.query.filter_by(store_id=store.id).count()

    return render_template("dashboard/orders.html",
                           store=store, orders=orders,
                           counts=counts, active_status=status,
                           OrderStatus=OrderStatus)


# ── Detalhe do pedido ─────────────────────────────────────────────────────────

@orders_bp.route("/stores/<int:store_id>/orders/<int:order_id>")
@login_required
def order_detail(store_id, order_id):
    store = _get_owned_store(store_id)
    order = Order.query.filter_by(id=order_id, store_id=store.id).first_or_404()
    return render_template("dashboard/order_detail.html",
                           store=store, order=order, OrderStatus=OrderStatus)


# ── Atualizar status ──────────────────────────────────────────────────────────

@orders_bp.route("/stores/<int:store_id>/orders/<int:order_id>/status",
                 methods=["POST"])
@login_required
def update_status(store_id, order_id):
    store  = _get_owned_store(store_id)
    order  = Order.query.filter_by(id=order_id, store_id=store.id).first_or_404()
    new_st = request.form.get("status", "").strip()

    if new_st not in order.next_statuses:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Transição inválida"}), 400
        flash("Transição de status inválida.", "error")
        return redirect(url_for("orders.order_detail",
                                store_id=store_id, order_id=order_id))

    # Se cancelado, devolve estoque
    if new_st == OrderStatus.CANCELLED and order.status != OrderStatus.CANCELLED:
        from ..models import Product
        for item in order.items:
            product = Product.query.get(item.product_id)
            if product:
                product.stock_quantity = product.effective_stock + item.quantity
                product.stock          = product.stock_quantity

    order.status = new_st
    db.session.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "status": new_st,
                        "label": order.status_label,
                        "color": order.status_color})

    flash(f'Status atualizado para "{order.status_label}".', "success")
    return redirect(url_for("orders.order_detail",
                            store_id=store_id, order_id=order_id))


# ── Adicionar nota interna ────────────────────────────────────────────────────

@orders_bp.route("/stores/<int:store_id>/orders/<int:order_id>/notes",
                 methods=["POST"])
@login_required
def add_note(store_id, order_id):
    store = _get_owned_store(store_id)
    order = Order.query.filter_by(id=order_id, store_id=store.id).first_or_404()
    note  = request.form.get("notes", "").strip()
    order.notes = note
    db.session.commit()
    flash("Nota salva.", "success")
    return redirect(url_for("orders.order_detail",
                            store_id=store_id, order_id=order_id))
