import uuid
from unittest.mock import patch


def _login(client, app):
    from passlib.apache import HtpasswdFile

    ht = HtpasswdFile(app.config["HTPASSWD_PATH"], new=True)
    ht.set_password("host", "pw")
    ht.save()
    client.post("/admin/login", data={"username": "host", "password": "pw"})


def test_qr_endpoint_returns_png(client, app):
    _login(client, app)
    resp = client.get(f"/admin/qr/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_qr_rejects_bad_uuid(client, app):
    _login(client, app)
    resp = client.get("/admin/qr/not-a-uuid")
    assert resp.status_code == 404


def test_qr_requires_login(client):
    resp = client.get(f"/admin/qr/{uuid.uuid4()}")
    assert resp.status_code == 302


def test_landing_with_valid_code_renders_form(client):
    invitee = {
        "id": uuid.uuid4(),
        "primary_name": "Alice Example",
        "rsvp_status": "Pending",
        "max_guests": 2,
        "plus_one_details": None,
        "comments": None,
        "lookup_phrase": "apple-sky-boat",
        "email": None,
    }
    with patch("rsvp.routes_public.db") as mock_db:
        mock_db.fetch_invitee_by_id.return_value = invitee
        resp = client.get(f"/?code={invitee['id']}")
    assert resp.status_code == 200
    assert b"Alice Example" in resp.data


def test_phrase_lookup_normalizes_input(client):
    with patch("rsvp.routes_public.db") as mock_db:
        mock_db.fetch_invitee_by_phrase.return_value = None
        client.post("/", data={"phrase": "  Apple Sky Boat "})
    mock_db.fetch_invitee_by_phrase.assert_called_once_with("apple-sky-boat")
