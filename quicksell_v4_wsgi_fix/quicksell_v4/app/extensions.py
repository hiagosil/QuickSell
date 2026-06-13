"""
Store Generator - Extensões Flask
Inicializadas aqui e depois ligadas ao app via init_app() para evitar imports circulares.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Faça login para acessar esta página."
