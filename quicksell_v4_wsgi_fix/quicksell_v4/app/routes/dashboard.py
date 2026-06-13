"""
QuickSell - Rotas: Dashboard e criação de lojas
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Store, Product
from ..utils.helpers import slugify

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard_index():
    """Página principal do usuário listando todas as suas lojas."""
    stores = Store.query.filter_by(user_id=current_user.id).order_by(Store.created_at.desc()).all()
    total_products = db.session.query(db.func.count(Product.id))\
        .join(Store).filter(Store.user_id == current_user.id).scalar() or 0

    return render_template("dashboard/index.html", stores=stores, total_products=total_products)


@dashboard_bp.route("/create-store", methods=["GET", "POST"])
@login_required
def create_store():
    """Exibe formulário e processa criação de nova loja."""
    if request.method == "POST":
        name        = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category    = request.form.get("category", "").strip()
        style       = request.form.get("style", "minimalista")
        # Usa a cor final (custom ou preset) enviada pelo JS
        color       = request.form.get("primary_color_final", "#7c5cfc").strip()

        # Validações básicas
        if not name:
            flash("O nome da loja é obrigatório.", "error")
            return render_template("dashboard/create_store.html")

        if style not in ("minimalista", "dark", "neon"):
            style = "minimalista"

        if not color.startswith("#") or len(color) != 7:
            color = "#7c5cfc"

        # Slug único
        base_slug = slugify(name)
        slug = _unique_slug(base_slug)

        store = Store(
            name=name,
            slug=slug,
            description=description,
            category=category,
            style=style,
            primary_color=color,
            user_id=current_user.id,
        )

        db.session.add(store)
        db.session.commit()

        flash(f'Loja "{name}" criada com sucesso! 🎉', "success")
        return redirect(url_for("dashboard.dashboard_index"))

    return render_template("dashboard/create_store.html")


@dashboard_bp.route("/stores/<int:store_id>/edit", methods=["GET", "POST"])
@login_required
def edit_store(store_id):
    """Edita uma loja existente do usuário."""
    store = _get_owned_store(store_id)

    if request.method == "POST":
        name        = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category    = request.form.get("category", "").strip()
        style       = request.form.get("style", "minimalista")
        color       = request.form.get("primary_color_final", store.primary_color).strip()
        is_active   = request.form.get("is_active") == "on"

        if not name:
            flash("O nome da loja é obrigatório.", "error")
            return render_template("dashboard/edit_store.html", store=store)

        if style not in ("minimalista", "dark", "neon"):
            style = store.style

        if not color.startswith("#") or len(color) != 7:
            color = store.primary_color

        store.name        = name
        store.description = description
        store.category    = category
        store.style       = style
        store.primary_color = color
        store.is_active   = is_active

        db.session.commit()
        flash("Loja atualizada com sucesso.", "success")
        return redirect(url_for("dashboard.dashboard_index"))

    return render_template("dashboard/edit_store.html", store=store)


@dashboard_bp.route("/stores/<int:store_id>/delete", methods=["POST"])
@login_required
def delete_store(store_id):
    """Remove uma loja e todos os seus produtos."""
    store = _get_owned_store(store_id)
    name = store.name
    db.session.delete(store)
    db.session.commit()
    flash(f'Loja "{name}" removida.', "info")
    return redirect(url_for("dashboard.dashboard_index"))


# ── Helpers ──────────────────────────────────────────────

def _get_owned_store(store_id: int) -> Store:
    """Busca loja garantindo que pertence ao usuário logado."""
    store = Store.query.filter_by(id=store_id, user_id=current_user.id).first()
    if not store:
        abort(404)
    return store


def _unique_slug(base: str) -> str:
    """Adiciona sufixo numérico se o slug já existir."""
    slug, counter = base, 1
    while Store.query.filter_by(slug=slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug
