"""Public guest-facing routes."""
import base64
import re
import uuid

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)

from . import db, phrases, services

bp = Blueprint("public", __name__)

VALID_STATUSES = {"Attending", "Declined"}
PHRASE_RE = re.compile(r"^[a-z]+-[a-z]+-[a-z]+$")
MAX_SELF_REGISTER_NAME_LEN = 200
MAX_SELF_REGISTER_GUESTS = 20  # sanity cap on public input, not a security boundary


def _honeypot_tripped(form):
    return bool(form.get("honeypot", "").strip())


def _parse_uuid(value):
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return None


@bp.get("/")
def landing():
    """Tier 1: ?code=UUID from the QR code. Otherwise show the
    Tier 2 phrase entry form."""
    code = request.args.get("code")
    if code:
        invitee_id = _parse_uuid(code)
        if invitee_id:
            invitee = db.fetch_invitee_by_id(invitee_id)
            if invitee:
                return render_template("rsvp_form.html", invitee=invitee)
        return render_template(
            "phrase_entry.html",
            error="That link didn't match an invitation. "
            "Try entering your passcode below.",
        )
    return render_template("phrase_entry.html", error=None)


@bp.post("/")
def phrase_lookup():
    """Tier 2: guest types their 3-word phrase."""
    if _honeypot_tripped(request.form):
        return render_template("phrase_entry.html", error=None), 200

    phrase = phrases.normalize_phrase(request.form.get("phrase", ""))

    anonymous_raw = current_app.config.get("ANONYMOUS_PHRASE", "")
    if (
        anonymous_raw
        and phrase
        and phrase == phrases.normalize_phrase(anonymous_raw)
    ):
        return render_template("self_register.html", error=None)

    if not PHRASE_RE.match(phrase):
        return render_template(
            "phrase_entry.html",
            error="Passcodes are three words, like apple-sky-boat.",
        )

    invitee = db.fetch_invitee_by_phrase(phrase)
    if not invitee:
        return render_template(
            "phrase_entry.html",
            error="That passcode didn't match. Check your card and try again.",
        )
    return render_template("rsvp_form.html", invitee=invitee)


@bp.post("/rsvp")
def submit_rsvp():
    if _honeypot_tripped(request.form):
        return redirect(url_for("public.thanks"))

    invitee_id = _parse_uuid(request.form.get("invitee_id"))
    status = request.form.get("rsvp_status", "")
    plus_ones = request.form.get("plus_one_details", "").strip()[:1000]
    comments = request.form.get("comments", "").strip()[:2000]

    if not invitee_id or status not in VALID_STATUSES:
        return redirect(url_for("public.landing"))

    invitee = db.fetch_invitee_by_id(invitee_id)
    if not invitee:
        return redirect(url_for("public.landing"))

    if invitee["max_guests"] == 0:
        plus_ones = ""

    db.update_rsvp(invitee_id, status, plus_ones, comments)
    return redirect(url_for("public.thanks"))


@bp.post("/self-register")
def self_register_submit():
    """Public self-registration, reached only when a visitor's typed
    phrase matched the configured ANONYMOUS_PHRASE (see phrase_lookup).
    Structurally the public, unauthenticated equivalent of
    routes_admin.add_invitee: creates a real invitee row immediately
    (origin='self') and hands back the real credential (phrase/link/QR)
    on screen and by email, instead of requiring admin approval first."""
    if _honeypot_tripped(request.form):
        return render_template("self_register.html", error=None), 200

    cfg = current_app.config
    anonymous_raw = cfg.get("ANONYMOUS_PHRASE", "")
    if not anonymous_raw:
        # Defense in depth: this endpoint is public and directly
        # POST-able regardless of how the visitor got here; refuse to
        # create anything if the feature is disabled.
        return redirect(url_for("public.landing"))

    name = (request.form.get("primary_name") or "").strip()[:MAX_SELF_REGISTER_NAME_LEN]
    if not name:
        return render_template("self_register.html", error="Please tell us your name.")

    email = (request.form.get("email") or "").strip()[:320]

    try:
        max_guests = int((request.form.get("max_guests") or "0").strip() or 0)
    except ValueError:
        max_guests = 0
    max_guests = max(0, min(max_guests, MAX_SELF_REGISTER_GUESTS))

    invitee_id, phrase = phrases.insert_with_unique_phrase(
        db.insert_self_invitee, name, email, max_guests
    )

    url = services.invite_url(cfg["DOMAIN_NAME"], invitee_id)
    qr_data_uri = "data:image/png;base64," + base64.b64encode(
        services.qr_png_bytes(url)
    ).decode("ascii")

    email_sent = bool(email and "@" in email)
    if email_sent:
        try:
            services.send_self_registration_email(
                cfg["AWS_REGION"], cfg["SES_SENDER_EMAIL"], email, url, phrase
            )
        except Exception:
            current_app.logger.exception("SES send failed")

    return render_template(
        "self_register_confirm.html",
        primary_name=name,
        phrase=phrase,
        url=url,
        qr_data_uri=qr_data_uri,
        email_sent=email_sent,
    )


@bp.get("/thanks")
def thanks():
    return render_template("thanks.html")


@bp.get("/recover")
def recover_form():
    return render_template("recover.html", submitted=False)


@bp.post("/recover")
def recover_submit():
    """Tier 3: email recovery. Always shows the same message whether or
    not the email matched (silent fail against enumeration)."""
    if _honeypot_tripped(request.form):
        return render_template("recover.html", submitted=True)

    email = request.form.get("email", "").strip()
    if email and "@" in email:
        invitee = db.fetch_invitee_by_email(email)
        if invitee and invitee.get("email"):
            cfg = current_app.config
            url = services.invite_url(cfg["DOMAIN_NAME"], invitee["id"])
            try:
                services.send_recovery_email(
                    cfg["AWS_REGION"],
                    cfg["SES_SENDER_EMAIL"],
                    invitee["email"],
                    url,
                    invitee["lookup_phrase"],
                )
            except Exception:
                current_app.logger.exception("SES send failed")
    return render_template("recover.html", submitted=True)
