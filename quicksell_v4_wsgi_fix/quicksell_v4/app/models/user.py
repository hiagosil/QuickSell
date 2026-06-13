"""
Store Generator - Modelo: User
"""

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento: um usuário pode ter várias lojas
    stores = db.relationship("Store", backref="owner", lazy=True, cascade="all, delete-orphan")

    # --- Métodos de senha ---

    def set_password(self, password: str):
        """Gera hash seguro da senha antes de salvar."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica se a senha fornecida bate com o hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


# Flask-Login precisa saber como carregar um usuário pelo ID
@login_manager.user_loader
def load_user(user_id: int):
    return User.query.get(int(user_id))
