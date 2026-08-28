import uuid
from unittest.mock import patch


def _login(client, app):
    from passlib.apache import HtpasswdFile

    ht = HtpasswdFile(app.config["HTPASSWD_PATH"], new=True)
    ht.set_password("host", "pw")
    ht.save()
    client.post("/admin/login", data={"username": "host", "password": "pw"})


# --- auth gating -----------------------------------------------------

def test_bulk_confirm_requires_login(client):
    resp = client.post("/admin/bulk-confirm", data={"invitee_ids": [str(uuid.uuid4())]})
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("Location", "")


def test_bulk_delete_requires_login(client):
    resp = client.post("/admin/bulk-delete", data={"invitee_ids": [str(uuid.uuid4())]})
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("Location", "")


def test_export_csv_requires_login(client):
    resp = client.post("/admin/export-csv")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("Location", "")


# --- bulk confirm ------------------------------------------------------

def test_bulk_confirm_marks_selected_ids_reviewed(client, app):
    _login(client, app)
    id1, id2 = uuid.uuid4(), uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.bulk_mark_reviewed.return_value = 2
        resp = client.post(
            "/admin/bulk-confirm", data={"invitee_ids": [str(id1), str(id2)]}
        )
    assert resp.status_code == 302
    (called_ids,), _ = mock_db.bulk_mark_reviewed.call_args
    assert set(called_ids) == {id1, id2}


def test_bulk_confirm_with_no_selection_does_nothing(client, app):
    _login(client, app)
    with patch("rsvp.routes_admin.db") as mock_db:
        resp = client.post("/admin/bulk-confirm", data={})
    assert resp.status_code == 302
    mock_db.bulk_mark_reviewed.assert_not_called()


def test_bulk_confirm_drops_malformed_ids(client, app):
    _login(client, app)
    good_id = uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.bulk_mark_reviewed.return_value = 1
        resp = client.post(
            "/admin/bulk-confirm",
            data={"invitee_ids": [str(good_id), "not-a-uuid"]},
        )
    assert resp.status_code == 302
    (called_ids,), _ = mock_db.bulk_mark_reviewed.call_args
    assert called_ids == [good_id]


# --- bulk delete ------------------------------------------------------

def test_bulk_delete_removes_selected_ids(client, app):
    _login(client, app)
    id1, id2 = uuid.uuid4(), uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.bulk_delete_invitees.return_value = 2
        resp = client.post(
            "/admin/bulk-delete", data={"invitee_ids": [str(id1), str(id2)]}
        )
    assert resp.status_code == 302
    (called_ids,), _ = mock_db.bulk_delete_invitees.call_args
    assert set(called_ids) == {id1, id2}


def test_bulk_delete_with_no_selection_does_nothing(client, app):
    _login(client, app)
    with patch("rsvp.routes_admin.db") as mock_db:
        resp = client.post("/admin/bulk-delete", data={})
    assert resp.status_code == 302
    mock_db.bulk_delete_invitees.assert_not_called()


# --- CSV export ---------------------------------------------------------

def test_export_csv_all_when_none_selected(client, app):
    _login(client, app)
    row = {
        "primary_name": "Alice", "email": "alice@example.com", "rsvp_status": "Attending",
        "max_guests": 1, "plus_one_details": '[{"name": "Bob", "child": false}]',
        "comments": "yay", "lookup_phrase": "apple-sky-boat", "origin": "admin",
        "reviewed": True,
    }
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.fetch_all_invitees.return_value = [row]
        resp = client.post("/admin/export-csv", data={})
    assert resp.status_code == 200
    mock_db.fetch_all_invitees.assert_called_once()
    mock_db.fetch_invitees_by_ids.assert_not_called()
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    body = resp.data.decode("utf-8")
    assert "Alice" in body
    assert "alice@example.com" in body
    assert "Bob (child)" not in body  # Bob isn't a child in this fixture
    assert "Bob" in body


def test_export_csv_selected_ids_only(client, app):
    _login(client, app)
    target_id = uuid.uuid4()
    row = {
        "primary_name": "Charlie", "email": "", "rsvp_status": "Pending",
        "max_guests": 0, "plus_one_details": None,
        "comments": "", "lookup_phrase": "apple-sky-boat", "origin": "self",
        "reviewed": False,
    }
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.fetch_invitees_by_ids.return_value = [row]
        resp = client.post("/admin/export-csv", data={"invitee_ids": [str(target_id)]})
    assert resp.status_code == 200
    (called_ids,), _ = mock_db.fetch_invitees_by_ids.call_args
    assert called_ids == [target_id]
    mock_db.fetch_all_invitees.assert_not_called()
    assert "Charlie" in resp.data.decode("utf-8")


def test_export_csv_marks_child_guests(client, app):
    _login(client, app)
    row = {
        "primary_name": "Dana", "email": "", "rsvp_status": "Attending",
        "max_guests": 1, "plus_one_details": '[{"name": "Timmy", "child": true}]',
        "comments": "", "lookup_phrase": "apple-sky-boat", "origin": "admin",
        "reviewed": True,
    }
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.fetch_all_invitees.return_value = [row]
        resp = client.post("/admin/export-csv", data={})
    assert "Timmy (child)" in resp.data.decode("utf-8")
