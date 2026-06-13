"""
QuickSell - Utilitários de Upload de Imagens
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from flask import current_app
from werkzeug.utils import secure_filename


def allowed_file(filename: str) -> bool:
    """Verifica se a extensão do arquivo é permitida."""
    allowed = current_app.config.get("ALLOWED_EXTENSIONS", {"jpg", "jpeg", "png", "webp"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def save_product_image(file_storage) -> Optional[str]:
    """
    Salva o arquivo de imagem no disco.
    Retorna o nome do arquivo (relativo ao UPLOAD_FOLDER) ou None.
    """
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_file(file_storage.filename):
        return None

    ext      = file_storage.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)

    file_storage.save(os.path.join(upload_dir, filename))
    return filename


def delete_product_image(image_path: str) -> None:
    """Remove arquivo de imagem do disco, silenciosamente se não existir."""
    if not image_path:
        return
    full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], image_path)
    try:
        os.remove(full_path)
    except FileNotFoundError:
        pass
