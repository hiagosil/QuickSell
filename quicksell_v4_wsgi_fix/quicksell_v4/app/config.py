"""
QuickSell - Configurações por Ambiente (v4 — produção/Render)
"""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _normalize_db_url(url: str) -> str:
    """
    O Render (e o Heroku antigamente) fornece DATABASE_URL no formato
    'postgres://...', mas o SQLAlchemy 2.x exige o dialeto explícito
    'postgresql://...'. Sem essa normalização, db.create_all() falha
    com: sqlalchemy.exc.NoSuchModuleError: Can't load plugin: ... postgres
    """
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-troque-em-producao")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Upload ──────────────────────────────────────────────
    # NOTA: em hosts com disco efêmero (Render free tier), arquivos
    # salvos aqui são perdidos a cada deploy/restart. Aceito por ora —
    # migrar para S3/Cloudinary é trabalho futuro.
    UPLOAD_FOLDER      = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024          # 5 MB
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, '..', 'store_generator_dev.db')}"
    )
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(SQLALCHEMY_DATABASE_URI)


class ProductionConfig(BaseConfig):
    DEBUG = False

    _db_url = os.environ.get("DATABASE_URL", "")
    if not _db_url:
        # Fallback explícito — funciona, mas avisa no log que não há
        # persistência real configurada (disco efêmero).
        _db_url = f"sqlite:///{os.path.join(BASE_DIR, '..', 'store_generator.db')}"
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(_db_url)

    # Cookies de sessão seguros — exigido quando servido via HTTPS (Render sempre é)
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Proxy fix — Render roda detrás de um proxy/load balancer.
    # Sem isso, url_for(..., _external=True) e request.is_secure
    # podem gerar URLs http:// em vez de https:// (quebra webhook do MP).
    PREFERRED_URL_SCHEME = "https"


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":      TestingConfig,
}


def get_config_name() -> str:
    """
    Lê FLASK_ENV (ou ENV, fallback) para decidir qual config carregar.
    Render: definir FLASK_ENV=production nas env vars do serviço.
    Local: não definir — cai em 'development'.
    """
    return os.environ.get("FLASK_ENV", os.environ.get("ENV", "development")).lower()
