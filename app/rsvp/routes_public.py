"""Public guest-facing routes."""
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

from . import db, services

bp = Blueprint("public", __name__)

VALID_STATUSES = {"Attending", "Declined"}
PHRASE_RE = re.compile(r"^[a-z]+-[a-z]+-[a-z]+$")


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

    raw = request.form.get("phrase", "")
    phrase = "-".join(raw.strip().lower().replace("_", "-").split())
    phrase = re.sub(r"-+", "-", phrase)

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
