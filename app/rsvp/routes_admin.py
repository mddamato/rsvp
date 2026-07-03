"""Admin portal routes."""
import csv
import io
import uuid

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

from . import auth, db, phrases, services

bp = Blueprint("admin", __name__, url_prefix="/admin")


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
