"""
QuickSell v3 - Rotas: Loja Pública (passa summary do carrinho para o template)
"""
from flask import Blueprint, render_template, abort, request
from ..models import Store, Product, Category
from ..utils.cart import cart_summary

store_public_bp = Blueprint("store_public", __name__)

STYLE_TEMPLATES = {
    "minimalista": "store/minimalista.html",
    "dark":        "store/dark.html",
    "neon":        "store/neon.html",
}


@store_public_bp.route("/store/<slug>")
def view_store(slug):
    store = Store.query.filter_by(slug=slug, is_active=True).first()
    if not store:
        abort(404)

    cat_filter = request.args.get("cat", type=int)
    q = Product.query.filter_by(store_id=store.id, is_active=True)
    if cat_filter:
        q = q.filter_by(category_id=cat_filter)

    products   = q.order_by(Product.created_at.desc()).all()
    categories = Category.query.filter_by(store_id=store.id).order_by(Category.name).all()
    summary    = cart_summary(slug)

    template = STYLE_TEMPLATES.get(store.style, STYLE_TEMPLATES["minimalista"])
    return render_template(template, store=store, products=products,
                           categories=categories, active_cat=cat_filter,
                           summary=summary)
