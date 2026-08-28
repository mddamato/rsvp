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
        EVENT_CLOSING=os.environ.get("EVENT_CLOSING", ""),
        EVENT_DETAILS_IMAGE=os.environ.get("EVENT_DETAILS_IMAGE", ""),
        ANONYMOUS_PHRASE=os.environ.get("ANONYMOUS_PHRASE", ""),
        SELF_REGISTER_MULTIPLE_GUESTS=os.environ.get("SELF_REGISTER_MULTIPLE_GUESTS", "0") == "1",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_DEBUG") != "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2MB cap, plenty for a guest CSV
    )

    if test_config:
        app.config.update(test_config)

    from . import guests, routes_public, routes_admin, services

    app.register_blueprint(routes_public.bp)
    app.register_blueprint(routes_admin.bp)
    app.jinja_env.filters["parse_guests"] = guests.parse_guests

    # Computed once (not per-request) and injected into every template
    # automatically, so a template can reference these without every
    # render_template() call needing to pass them explicitly -- notably
    # so self_register.html gets a valid register_token whether it was
    # reached by typing the correct phrase or via a tokened /register
    # link, with no special-casing needed per entry point.
    image_token = services.event_image_token(app.config["SECRET_KEY"])
    reg_token = services.register_token(app.config["SECRET_KEY"])
    app.context_processor(lambda: {"event_image_token": image_token, "register_token": reg_token})

    return app
