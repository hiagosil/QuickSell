"""
QuickSell v3 - Utilitário de Carrinho de Compras

Estrutura da sessão:
    session['cart_<slug>'] = {
        "<product_id>": {"qty": int, "name": str, "price": float, "image": Optional[str], "sku": str}
    }

NOTA DE ARQUITETURA — import circular:
    cart.py NÃO importa de models/ no topo do módulo.
    As funções que precisam de um Product recebem o objeto já instanciado
    pelas rotas. Type hints usam TYPE_CHECKING para documentação sem
    executar o import em runtime.

NOTA — summary.items vs dict.items():
    cart_summary() retorna um objeto CartSummary (não um dict puro).
    Isso evita a ambiguidade fatal do Jinja2:
        {{ summary.items }}  →  Jinja tenta getattr primeiro
                             →  dict.items é um método builtin
                             →  TypeError: 'builtin_function_or_method' is not iterable

    Com CartSummary, summary.items é um atributo real (lista), não um método.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from flask import session

if TYPE_CHECKING:
    from ..models.product import Product


# ── CartSummary — objeto com atributos reais ────────────────────────────────
# Resolver o bug: Jinja2 usa getattr antes de getitem ao acessar summary.items
# Se summary for um dict, summary.items resolve para o método builtin dict.items
# Se summary for um objeto, summary.items resolve para a lista real

class CartItem:
    """Representa um item serializado do carrinho (sem acesso ao banco)."""

    __slots__ = ("product_id", "name", "price", "qty", "image", "sku", "line_total")

    def __init__(self, product_id: int, name: str, price: float,
                 qty: int, image: Optional[str], sku: str):
        self.product_id = product_id
        self.name       = name
        self.price      = price
        self.qty        = qty
        self.image      = image
        self.sku        = sku
        self.line_total = round(price * qty, 2)


class CartSummary:
    """
    Resumo do carrinho retornado por cart_summary().

    Atributos acessíveis em Jinja2 via ponto sem ambiguidade:
        {{ summary.items }}      → lista de CartItem
        {{ summary.subtotal }}   → float
        {{ summary.shipping }}   → float
        {{ summary.total }}      → float
        {{ summary.item_count }} → int
    """

    __slots__ = ("items", "subtotal", "shipping", "total", "item_count")

    def __init__(self, items: List[CartItem], subtotal: float,
                 shipping: float, total: float, item_count: int):
        self.items      = items
        self.subtotal   = subtotal
        self.shipping   = shipping
        self.total      = total
        self.item_count = item_count


# ── chave de sessão ─────────────────────────────────────────────────────────

def _key(slug: str) -> str:
    return f"cart_{slug}"


# ── leitura ──────────────────────────────────────────────────────────────────

def get_cart(slug: str) -> dict:
    """Retorna o dict interno do carrinho (cópia)."""
    return dict(session.get(_key(slug), {}))


# ── escrita ──────────────────────────────────────────────────────────────────

def add_to_cart(slug: str, product: "Product", qty: int = 1) -> dict:
    """Adiciona ou incrementa produto. Respeita estoque disponível."""
    cart        = get_cart(slug)
    pid         = str(product.id)
    current_qty = cart[pid]["qty"] if pid in cart else 0
    new_qty     = min(current_qty + qty, product.effective_stock)

    if new_qty <= 0:
        cart.pop(pid, None)
    else:
        cart[pid] = {
            "qty":   new_qty,
            "name":  product.name,
            "price": float(product.price),
            "image": product.image,
            "sku":   product.sku or "",
        }

    session[_key(slug)] = cart
    session.modified    = True
    return cart


def remove_from_cart(slug: str, product_id: int) -> dict:
    """Remove um produto do carrinho."""
    cart = get_cart(slug)
    cart.pop(str(product_id), None)
    session[_key(slug)] = cart
    session.modified    = True
    return cart


def update_cart_qty(slug: str, product: "Product", qty: int) -> dict:
    """Define a quantidade exata de um produto."""
    cart = get_cart(slug)
    pid  = str(product.id)

    if qty <= 0:
        cart.pop(pid, None)
    else:
        cart[pid] = {
            "qty":   min(qty, product.effective_stock),
            "name":  product.name,
            "price": float(product.price),
            "image": product.image,
            "sku":   product.sku or "",
        }

    session[_key(slug)] = cart
    session.modified    = True
    return cart


def clear_cart(slug: str) -> None:
    """Esvazia o carrinho."""
    session.pop(_key(slug), None)
    session.modified = True


# ── resumo ───────────────────────────────────────────────────────────────────

def cart_summary(slug: str) -> CartSummary:
    """
    Retorna um CartSummary com atributos reais — não um dict puro.

    Por que CartSummary e não dict?
    ─────────────────────────────────
    Jinja2 resolve {{ summary.items }} tentando getattr() ANTES de getitem().
    Um dict Python tem dict.items como método builtin — Jinja encontra esse
    método e tenta iterar sobre ele, causando:
        TypeError: 'builtin_function_or_method' object is not iterable

    Com CartSummary, summary.items é um atributo de instância (lista real),
    e getattr() retorna a lista corretamente.
    """
    cart     = get_cart(slug)
    items    = []
    subtotal = 0.0

    for pid, data in cart.items():
        line_total = data["price"] * data["qty"]
        subtotal  += line_total
        items.append(CartItem(
            product_id = int(pid),
            name       = data["name"],
            price      = data["price"],
            qty        = data["qty"],
            image      = data.get("image"),
            sku        = data.get("sku", ""),
        ))

    shipping = 0.0 if subtotal >= 150 else (15.0 if subtotal > 0 else 0.0)
    total    = subtotal + shipping

    return CartSummary(
        items      = items,
        subtotal   = round(subtotal, 2),
        shipping   = round(shipping, 2),
        total      = round(total, 2),
        item_count = sum(d["qty"] for d in cart.values()),
    )
