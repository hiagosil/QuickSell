"""
QuickSell - Rota principal: landing, health check, error handlers
"""

from flask import Blueprint, jsonify, render_template, redirect, url_for
from flask_login import current_user

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard_index"))
    return redirect(url_for("auth.login"))


@main_bp.route("/health")
def health():
    return jsonify({"status": "ok", "app": "QuickSell"}), 200


@main_bp.app_errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e)}), 404


@main_bp.app_errorhandler(403)
def forbidden(e):
    return jsonify({"error": str(e)}), 403


@main_bp.app_errorhandler(401)
def unauthorized(e):
    return jsonify({"error": "Autenticação necessária"}), 401
