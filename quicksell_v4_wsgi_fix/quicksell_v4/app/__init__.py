"""
QuickSell - Application Factory (v4 — Mercado Pago PIX + produção/Render)
"""
import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import db, login_manager
from .config import config, get_config_name


def create_app(env: str = None):
    """
    env: nome explícito da config ("development"/"production"/"testing").
    Se None, é lido de FLASK_ENV/ENV via get_config_name() — necessário
    para que `app = create_app()` em app.py escolha ProductionConfig
    quando FLASK_ENV=production estiver definido no Render.
    """
    if env is None:
        env = get_config_name()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[env])

    # ── Proxy fix ────────────────────────────────────────────────────────
    # Render (e a maioria dos PaaS) coloca a app detrás de um proxy reverso
    # que termina o TLS. Sem ProxyFix, request.scheme é "http" mesmo em
    # produção — isso quebra url_for(..., _external=True) usado para
    # montar a notification_url do webhook do Mercado Pago, gerando
    # callbacks http:// que o MP rejeita.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from .routes.main         import main_bp
    from .routes.auth         import auth_bp
    from .routes.dashboard    import dashboard_bp
    from .routes.product      import product_bp
    from .routes.category     import category_bp
    from .routes.store_public import store_public_bp
    from .routes.cart         import cart_bp
    from .routes.orders       import orders_bp
    from .routes.payment      import payment_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,         url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(store_public_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(payment_bp)

    with app.app_context():
        db.create_all()

    return app
