"""Admin portal routes."""
import csv
import io
import uuid
from datetime import date

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import auth, db, guests, phrases, services

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _parse_uuid_list(values):
    """Parse the dashboard's checked invitee_ids into real UUIDs,
    silently dropping anything malformed (a tampered or stale form
    field) rather than failing the whole bulk action."""
    result = []
    for v in values:
        try:
            result.append(uuid.UUID(v))
        except (ValueError, TypeError, AttributeError):
            continue
    return result


@bp.get("/login")
def login():
    return render_template("admin_login.html")


@bp.post("/login")
def login_submit():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    if auth.verify_credentials(username, password):
        session.clear()
        session["admin"] = username
        return redirect(url_for("admin.dashboard"))
    flash("Wrong username or password.")
    return render_template("admin_login.html"), 401


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@bp.get("/dashboard")
@auth.login_required
def dashboard():
    counts = db.dashboard_counts()
    invitees = db.fetch_all_invitees()
    return render_template(
        "admin_dashboard.html", counts=counts, invitees=invitees
    )


@bp.post("/upload-csv")
@auth.login_required
def upload_csv():
    """Bulk provisioning. Expected columns: primary_name, email, max_guests.
    Header row required. email and max_guests may be blank."""
    file = request.files.get("csv_file")
    if not file or not file.filename:
        flash("Choose a CSV file first.")
        return redirect(url_for("admin.dashboard"))

    try:
        text = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("That file isn't valid UTF-8 text.")
        return redirect(url_for("admin.dashboard"))

    reader = csv.DictReader(io.StringIO(text))
    created, skipped = 0, 0
    for row in reader:
        name = (row.get("primary_name") or "").strip()
        if not name:
            skipped += 1
            continue
        email = (row.get("email") or "").strip()
        try:
            max_guests = int((row.get("max_guests") or "0").strip() or 0)
        except ValueError:
            max_guests = 0
        phrases.insert_with_unique_phrase(
            db.insert_invitee, name, email, max_guests
        )
        created += 1

    flash(f"Created {created} invitees." + (f" Skipped {skipped} rows with no name." if skipped else ""))
    return redirect(url_for("admin.dashboard"))


@bp.post("/add-invitee")
@auth.login_required
def add_invitee():
    name = (request.form.get("primary_name") or "").strip()
    if not name:
        flash("Name is required.")
        return redirect(url_for("admin.dashboard"))

    email = (request.form.get("email") or "").strip()
    try:
        max_guests = int((request.form.get("max_guests") or "0").strip() or 0)
    except ValueError:
        max_guests = 0

    phrases.insert_with_unique_phrase(db.insert_invitee, name, email, max_guests)
    flash(f"Added {name}.")
    return redirect(url_for("admin.dashboard"))


@bp.get("/edit/<invitee_id>")
@auth.login_required
def edit_invitee_form(invitee_id):
    try:
        parsed = uuid.UUID(invitee_id)
    except ValueError:
        return redirect(url_for("admin.dashboard"))
    invitee = db.fetch_invitee_by_id(parsed)
    if not invitee:
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_edit.html", invitee=invitee)


ADMIN_VALID_STATUSES = {"Pending", "Attending", "Declined"}  # unlike the guest form, admin can also reset to Pending


@bp.post("/edit/<invitee_id>")
@auth.login_required
def edit_invitee_submit(invitee_id):
    try:
        parsed = uuid.UUID(invitee_id)
    except ValueError:
        return redirect(url_for("admin.dashboard"))

    name = (request.form.get("primary_name") or "").strip()
    if not name:
        flash("Name is required.")
        return redirect(url_for("admin.edit_invitee_form", invitee_id=invitee_id))

    status = request.form.get("rsvp_status", "")
    if status not in ADMIN_VALID_STATUSES:
        flash("Invalid RSVP status.")
        return redirect(url_for("admin.edit_invitee_form", invitee_id=invitee_id))

    email = (request.form.get("email") or "").strip()
    try:
        max_guests = int((request.form.get("max_guests") or "0").strip() or 0)
    except ValueError:
        max_guests = 0
    comments = request.form.get("comments", "").strip()[:2000]
    guest_list = guests.guest_rows_from_form(request.form, max_guests)

    if not db.update_invitee(parsed, name, email, max_guests):
        flash("Guest not found.")
        return redirect(url_for("admin.dashboard"))
    # Reuses the same function submit_rsvp calls for a guest's own
    # edit, so an admin-made change gets the usual rsvp_history audit
    # row too, same as any other status change.
    db.update_rsvp(parsed, status, guests.serialize_guests(guest_list), comments, email)

    flash(f"Updated {name}.")
    return redirect(url_for("admin.dashboard"))


@bp.post("/delete/<invitee_id>")
@auth.login_required
def delete_invitee(invitee_id):
    try:
        parsed = uuid.UUID(invitee_id)
    except ValueError:
        return redirect(url_for("admin.dashboard"))

    if db.delete_invitee(parsed):
        flash("Guest deleted.")
    else:
        flash("Guest not found.")
    return redirect(url_for("admin.dashboard"))


@bp.post("/confirm/<invitee_id>")
@auth.login_required
def confirm_invitee(invitee_id):
    """Dismiss a self-registered guest's pending-review flag. They
    already have full access (self-registration grants it
    immediately) -- this is just admin bookkeeping."""
    try:
        parsed = uuid.UUID(invitee_id)
    except ValueError:
        return redirect(url_for("admin.dashboard"))

    if db.mark_invitee_reviewed(parsed):
        flash("Marked as reviewed.")
    else:
        flash("Guest not found.")
    return redirect(url_for("admin.dashboard"))


@bp.post("/bulk-confirm")
@auth.login_required
def bulk_confirm():
    ids = _parse_uuid_list(request.form.getlist("invitee_ids"))
    if not ids:
        flash("No guests selected.")
        return redirect(url_for("admin.dashboard"))
    count = db.bulk_mark_reviewed(ids)
    flash(f"Marked {count} guest(s) as reviewed.")
    return redirect(url_for("admin.dashboard"))


@bp.post("/bulk-delete")
@auth.login_required
def bulk_delete():
    ids = _parse_uuid_list(request.form.getlist("invitee_ids"))
    if not ids:
        flash("No guests selected.")
        return redirect(url_for("admin.dashboard"))
    count = db.bulk_delete_invitees(ids)
    flash(f"Deleted {count} guest(s).")
    return redirect(url_for("admin.dashboard"))


@bp.post("/export-csv")
@auth.login_required
def export_csv():
    """Downloads a CSV of the selected rows, or of every guest if none
    were checked -- so the same button works both as "export my
    selection" and "export everything"."""
    ids = _parse_uuid_list(request.form.getlist("invitee_ids"))
    invitees = db.fetch_invitees_by_ids(ids) if ids else db.fetch_all_invitees()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["primary_name", "email", "rsvp_status", "max_guests", "guests",
         "comments", "lookup_phrase", "origin", "reviewed"]
    )
    for g in invitees:
        guest_names = ", ".join(
            gu["name"] + (" (child)" if gu.get("child") else "")
            for gu in guests.parse_guests(g["plus_one_details"])
        )
        writer.writerow([
            g["primary_name"], g["email"] or "", g["rsvp_status"], g["max_guests"],
            guest_names, g["comments"] or "", g["lookup_phrase"], g["origin"], g["reviewed"],
        ])

    resp = Response(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f"attachment; filename=guests-{date.today().isoformat()}.csv"
    return resp


@bp.get("/card/<invitee_id>")
@auth.login_required
def card_view(invitee_id):
    """Print-ready view: QR code plus the 3-word phrase."""
    try:
        parsed = uuid.UUID(invitee_id)
    except ValueError:
        return redirect(url_for("admin.dashboard"))
    invitee = db.fetch_invitee_by_id(parsed)
    if not invitee:
        return redirect(url_for("admin.dashboard"))
    url = services.invite_url(current_app.config["DOMAIN_NAME"], invitee["id"])
    return render_template("admin_card.html", invitee=invitee, url=url)


@bp.get("/qr/<invitee_id>")
@auth.login_required
def qr_image(invitee_id):
    """QR code PNG generated in memory."""
    try:
        parsed = uuid.UUID(invitee_id)
    except ValueError:
        return Response(status=404)
    url = services.invite_url(current_app.config["DOMAIN_NAME"], parsed)
    png = services.qr_png_bytes(url)
    return Response(png, mimetype="image/png")


def _register_url(cfg):
    """The token makes /register (a static, otherwise-guessable path)
    unreachable to a blind bot -- only a link/QR generated here
    carries a valid one. See services.register_token."""
    token = services.register_token(cfg["SECRET_KEY"])
    return f"https://{cfg['DOMAIN_NAME']}/register?t={token}"


@bp.get("/register-qr")
@auth.login_required
def register_qr():
    """QR code PNG for the direct self-registration entry point
    (public.register_landing) -- for handing out to anonymous people,
    no 3-word phrase needed."""
    png = services.qr_png_bytes(_register_url(current_app.config))
    return Response(png, mimetype="image/png")


@bp.get("/register-card")
@auth.login_required
def register_card():
    """Print-ready view of the self-registration QR code."""
    return render_template("admin_register_card.html", url=_register_url(current_app.config))
