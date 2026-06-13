"""
QuickSell - Rotas: Produtos (v2 — upload de imagem, SKU, categoria, estoque)
"""

import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Store, Product, Category
from ..utils.upload import save_product_image, delete_product_image

product_bp = Blueprint("product", __name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_owned_store(store_id: int) -> Store:
    store = Store.query.filter_by(id=store_id, user_id=current_user.id).first()
    if not store:
        abort(404)
    return store


def _get_product(product_id: int, store_id: int) -> Product:
    product = Product.query.filter_by(id=product_id, store_id=store_id).first()
    if not product:
        abort(404)
    return product


def _parse_product_form(store_id: int):
    """Extrai e valida campos do formulário de produto. Retorna dict ou None."""
    name      = request.form.get("name", "").strip()
    price_raw = request.form.get("price", "").strip()
    desc      = request.form.get("description", "").strip()
    image_url = request.form.get("image_url", "").strip()
    stock_raw = request.form.get("stock_quantity", request.form.get("stock", "0")).strip()
    sku       = request.form.get("sku", "").strip()
    cat_id    = request.form.get("category_id", "").strip()
    is_active = request.form.get("is_active") == "on"

    if not name:
        flash("O nome do produto é obrigatório.", "error")
        return None

    try:
        price = float(price_raw.replace(",", "."))
        if price < 0:
            raise ValueError
    except ValueError:
        flash("Preço inválido. Use números positivos (ex: 29.90).", "error")
        return None

    try:
        stock = int(stock_raw)
        stock = max(0, stock)
    except ValueError:
        stock = 0

    category_id = int(cat_id) if cat_id.isdigit() else None

    return dict(
        name=name, price=price, description=desc,
        image_url=image_url or None,
        stock_quantity=stock, stock=stock,
        sku=sku or None,
        category_id=category_id,
        is_active=is_active,
    )


# ── Listagem ─────────────────────────────────────────────────────────────────

@product_bp.route("/stores/<int:store_id>/products")
@login_required
def list_products(store_id):
    store      = _get_owned_store(store_id)
    products   = Product.query.filter_by(store_id=store_id)\
                    .order_by(Product.created_at.desc()).all()
    categories = Category.query.filter_by(store_id=store_id).order_by(Category.name).all()
    return render_template(
        "dashboard/products.html",
        store=store, products=products, categories=categories,
    )


# ── Criar produto ─────────────────────────────────────────────────────────────

@product_bp.route("/stores/<int:store_id>/products/new", methods=["POST"])
@login_required
def create_product(store_id):
    store = _get_owned_store(store_id)
    data  = _parse_product_form(store_id)

    if data is None:
        return redirect(url_for("product.list_products", store_id=store_id))

    product = Product(store_id=store.id, **data)

    # ── Upload de imagem ─────────────────────────
    uploaded = request.files.get("image_file")
    if uploaded and uploaded.filename:
        img_path = save_product_image(uploaded)
        if img_path:
            product.image_path = img_path
            product.image_url  = None   # prioriza upload local
        else:
            flash("Formato de imagem inválido. Use JPG, PNG ou WEBP (máx 5 MB).", "error")
            return redirect(url_for("product.list_products", store_id=store_id))

    db.session.add(product)
    db.session.commit()
    flash(f'Produto "{product.name}" adicionado!', "success")
    return redirect(url_for("product.list_products", store_id=store_id))


# ── Editar produto ────────────────────────────────────────────────────────────

@product_bp.route("/stores/<int:store_id>/products/<int:product_id>/edit",
                  methods=["GET", "POST"])
@login_required
def edit_product(store_id, product_id):
    store      = _get_owned_store(store_id)
    product    = _get_product(product_id, store.id)
    categories = Category.query.filter_by(store_id=store_id).order_by(Category.name).all()

    if request.method == "POST":
        data = _parse_product_form(store_id)
        if data is None:
            return render_template("dashboard/edit_product.html",
                                   store=store, product=product, categories=categories)

        # ── Upload de imagem ─────────────────────
        uploaded = request.files.get("image_file")
        if uploaded and uploaded.filename:
            img_path = save_product_image(uploaded)
            if img_path:
                # Remove imagem anterior se era upload local
                if product.image_path:
                    delete_product_image(product.image_path)
                data["image_path"] = img_path
                data["image_url"]  = None
            else:
                flash("Formato de imagem inválido. Use JPG, PNG ou WEBP (máx 5 MB).", "error")
                return render_template("dashboard/edit_product.html",
                                       store=store, product=product, categories=categories)
        elif data["image_url"] != (product.image_url or ""):
            # URL externa mudou — descarta upload local anterior
            if product.image_path and not uploaded:
                delete_product_image(product.image_path)
                data["image_path"] = None

        for k, v in data.items():
            setattr(product, k, v)

        db.session.commit()
        flash("Produto atualizado.", "success")
        return redirect(url_for("product.list_products", store_id=store_id))

    return render_template("dashboard/edit_product.html",
                           store=store, product=product, categories=categories)


# ── Deletar produto ───────────────────────────────────────────────────────────

@product_bp.route("/stores/<int:store_id>/products/<int:product_id>/delete",
                  methods=["POST"])
@login_required
def delete_product(store_id, product_id):
    store   = _get_owned_store(store_id)
    product = _get_product(product_id, store.id)
    name    = product.name

    if product.image_path:
        delete_product_image(product.image_path)

    db.session.delete(product)
    db.session.commit()
    flash(f'Produto "{name}" removido.', "info")
    return redirect(url_for("product.list_products", store_id=store_id))


# ── Toggle ativo/inativo ──────────────────────────────────────────────────────

@product_bp.route("/stores/<int:store_id>/products/<int:product_id>/toggle",
                  methods=["POST"])
@login_required
def toggle_product(store_id, product_id):
    store   = _get_owned_store(store_id)
    product = _get_product(product_id, store.id)

    product.is_active = not product.is_active
    db.session.commit()
    status = "ativado" if product.is_active else "desativado"
    flash(f'"{product.name}" {status}.', "info")
    return redirect(url_for("product.list_products", store_id=store_id))


# ── Ajuste rápido de estoque ──────────────────────────────────────────────────

@product_bp.route("/stores/<int:store_id>/products/<int:product_id>/stock",
                  methods=["POST"])
@login_required
def update_stock(store_id, product_id):
    """Ajuste rápido de estoque direto da tabela."""
    store   = _get_owned_store(store_id)
    product = _get_product(product_id, store.id)

    try:
        qty = int(request.form.get("quantity", 0))
        product.stock_quantity = max(0, qty)
        product.stock          = product.stock_quantity
        db.session.commit()
        flash(f'Estoque de "{product.name}" atualizado para {product.stock_quantity} un.', "success")
    except (ValueError, TypeError):
        flash("Quantidade inválida.", "error")

    return redirect(url_for("product.list_products", store_id=store_id))
