"""
Store Generator - Utilitários gerais
"""

import re
import unicodedata


def slugify(text: str) -> str:
    """
    Converte texto em slug URL-friendly.
    Ex: "Minha Loja Incrível!" -> "minha-loja-incrivel"
    """
    # Normaliza acentos (ex: "é" -> "e")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Lowercase e substitui espaços/chars especiais por hífens
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = text.strip("-")

    return text
