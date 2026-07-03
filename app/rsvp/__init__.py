"""RSVP application factory."""
import os

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DOMAIN_NAME=os.environ.get("DOMAIN_NAME", "localhost"),
        SES_SENDER_EMAIL=os.environ.get("SES_SENDER_EMAIL", ""),
        AWS_REGION=os.environ.get("AWS_REGION", "us-east-1"),
        HTPASSWD_PATH=os.environ.get("HTPASSWD_PATH", "/etc/rsvp/.htpasswd"),
        EVENT_TITLE=os.environ.get("EVENT_TITLE", "Our Celebration"),
        EVENT_SUBHEADING=os.environ.get("EVENT_SUBHEADING", ""),
        EVENT_DETAILS=os.environ.get("EVENT_DETAILS", ""),
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_DEBUG") != "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2MB cap, plenty for a guest CSV
    )

    if test_config:
        app.config.update(test_config)

    from . import routes_public, routes_admin

    app.register_blueprint(routes_public.bp)
    app.register_blueprint(routes_admin.bp)

    return app
