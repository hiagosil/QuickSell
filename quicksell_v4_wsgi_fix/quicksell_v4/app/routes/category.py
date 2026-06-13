"""
QuickSell - Rotas: Categorias de Produtos
"""
from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Store, Category, Product
from ..utils.helpers import slugify

category_bp = Blueprint("category", __name__)


def _get_owned_store(store_id: int) -> Store:
    store = Store.query.filter_by(id=store_id, user_id=current_user.id).first()
    if not store:
        abort(404)
    return store


def _unique_cat_slug(base: str, store_id: int, exclude_id: Optional[int] = None) -> str:
    from typing import Optional   # local para não poluir o módulo
    slug, counter = base, 1
    while True:
        q = Category.query.filter_by(slug=slug, store_id=store_id)
        if exclude_id:
            q = q.filter(Category.id != exclude_id)
        if not q.first():
            return slug
        slug = f"{base}-{counter}"
        counter += 1


@category_bp.route("/stores/<int:store_id>/categories")
@login_required
def list_categories(store_id):
    store      = _get_owned_store(store_id)
    categories = Category.query.filter_by(store_id=store_id).order_by(Category.name).all()
    return render_template("dashboard/categories.html", store=store, categories=categories)


@category_bp.route("/stores/<int:store_id>/categories/new", methods=["POST"])
@login_required
def create_category(store_id):
    store = _get_owned_store(store_id)
    name  = request.form.get("name", "").strip()
    if not name:
        flash("O nome da categoria é obrigatório.", "error")
        return redirect(url_for("category.list_categories", store_id=store_id))

    slug = _unique_cat_slug(slugify(name), store_id)
    cat  = Category(name=name, slug=slug, store_id=store.id)
    db.session.add(cat)
    db.session.commit()
    flash(f'Categoria "{name}" criada.', "success")
    return redirect(url_for("category.list_categories", store_id=store_id))


@category_bp.route("/stores/<int:store_id>/categories/<int:cat_id>/edit", methods=["POST"])
@login_required
def edit_category(store_id, cat_id):
    store = _get_owned_store(store_id)
    cat   = Category.query.filter_by(id=cat_id, store_id=store.id).first_or_404()
    name  = request.form.get("name", "").strip()
    if not name:
        flash("O nome da categoria é obrigatório.", "error")
        return redirect(url_for("category.list_categories", store_id=store_id))

    cat.name = name
    cat.slug = _unique_cat_slug(slugify(name), store_id, exclude_id=cat_id)
    db.session.commit()
    flash(f'Categoria renomeada para "{name}".', "success")
    return redirect(url_for("category.list_categories", store_id=store_id))


@category_bp.route("/stores/<int:store_id>/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
def delete_category(store_id, cat_id):
    store = _get_owned_store(store_id)
    cat   = Category.query.filter_by(id=cat_id, store_id=store.id).first_or_404()

    # Desvincula produtos antes de deletar
    Product.query.filter_by(category_id=cat_id).update({"category_id": None})

    name = cat.name
    db.session.delete(cat)
    db.session.commit()
    flash(f'Categoria "{name}" removida.', "info")
    return redirect(url_for("category.list_categories", store_id=store_id))
