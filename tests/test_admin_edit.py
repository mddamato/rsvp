import uuid
from unittest.mock import patch


def _login(client, app):
    from passlib.apache import HtpasswdFile

    ht = HtpasswdFile(app.config["HTPASSWD_PATH"], new=True)
    ht.set_password("host", "pw")
    ht.save()
    client.post("/admin/login", data={"username": "host", "password": "pw"})


def test_edit_form_requires_login(client):
    resp = client.get(f"/admin/edit/{uuid.uuid4()}")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("Location", "")


def test_edit_submit_requires_login(client):
    resp = client.post(f"/admin/edit/{uuid.uuid4()}", data={"primary_name": "Alice"})
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("Location", "")


def test_edit_submit_requires_name(client, app):
    _login(client, app)
    invitee_id = uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        resp = client.post(
            f"/admin/edit/{invitee_id}",
            data={"primary_name": "  ", "rsvp_status": "Pending"},
        )
    assert resp.status_code == 302
    mock_db.update_invitee.assert_not_called()
    mock_db.update_rsvp.assert_not_called()


def test_edit_submit_requires_valid_rsvp_status(client, app):
    _login(client, app)
    invitee_id = uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        resp = client.post(
            f"/admin/edit/{invitee_id}",
            data={"primary_name": "Alice", "rsvp_status": "Maybe"},
        )
    assert resp.status_code == 302
    mock_db.update_invitee.assert_not_called()
    mock_db.update_rsvp.assert_not_called()


def test_edit_submit_can_reset_status_to_pending(client, app):
    # Only the admin form offers this -- the guest-facing form doesn't.
    _login(client, app)
    invitee_id = uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.update_invitee.return_value = True
        resp = client.post(
            f"/admin/edit/{invitee_id}",
            data={"primary_name": "Alice", "rsvp_status": "Pending"},
        )
    assert resp.status_code == 302
    mock_db.update_rsvp.assert_called_once_with(invitee_id, "Pending", "[]", "", "")


def test_edit_submit_updates_status_guests_notes_and_email(client, app):
    _login(client, app)
    invitee_id = uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.update_invitee.return_value = True
        resp = client.post(
            f"/admin/edit/{invitee_id}",
            data={
                "primary_name": "Alice Example",
                "email": "alice@example.com",
                "max_guests": "2",
                "rsvp_status": "Attending",
                "guest_name_1": "Bob Smith",
                "guest_child_1": "on",
                "comments": "Vegetarian",
            },
        )
    assert resp.status_code == 302
    mock_db.update_invitee.assert_called_once_with(
        invitee_id, "Alice Example", "alice@example.com", 2
    )
    mock_db.update_rsvp.assert_called_once_with(
        invitee_id,
        "Attending",
        '[{"name": "Bob Smith", "child": true}]',
        "Vegetarian",
        "alice@example.com",
    )


def test_edit_submit_guest_rows_capped_at_max_guests(client, app):
    _login(client, app)
    invitee_id = uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.update_invitee.return_value = True
        client.post(
            f"/admin/edit/{invitee_id}",
            data={
                "primary_name": "Alice",
                "max_guests": "1",
                "rsvp_status": "Pending",
                "guest_name_1": "Bob",
                "guest_name_2": "Should be ignored, beyond max_guests",
            },
        )
    mock_db.update_rsvp.assert_called_once_with(
        invitee_id, "Pending", '[{"name": "Bob", "child": false}]', "", ""
    )


def test_edit_submit_flashes_when_invitee_not_found(client, app):
    _login(client, app)
    invitee_id = uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.update_invitee.return_value = False
        resp = client.post(
            f"/admin/edit/{invitee_id}",
            data={"primary_name": "Alice", "rsvp_status": "Pending"},
        )
    assert resp.status_code == 302
    mock_db.update_rsvp.assert_not_called()
