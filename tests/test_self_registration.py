import uuid
from unittest.mock import patch


def _login(client, app):
    from passlib.apache import HtpasswdFile

    ht = HtpasswdFile(app.config["HTPASSWD_PATH"], new=True)
    ht.set_password("host", "pw")
    ht.save()
    client.post("/admin/login", data={"username": "host", "password": "pw"})


def test_anonymous_phrase_match_renders_self_register_form(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    with patch("rsvp.routes_public.db") as mock_db:
        resp = client.post("/", data={"phrase": "tony's THIRD  Birthday"})
    assert resp.status_code == 200
    assert b'name="primary_name"' in resp.data
    mock_db.fetch_invitee_by_phrase.assert_not_called()


def test_anonymous_phrase_disabled_by_default(client):
    # ANONYMOUS_PHRASE is unset in the base test app fixture.
    with patch("rsvp.routes_public.db") as mock_db:
        mock_db.fetch_invitee_by_phrase.return_value = None
        resp = client.post("/", data={"phrase": "Tonys third birthday"})
    assert resp.status_code == 200
    assert b'name="primary_name"' not in resp.data


def test_non_anonymous_non_matching_phrase_still_shows_error(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    with patch("rsvp.routes_public.db") as mock_db:
        mock_db.fetch_invitee_by_phrase.return_value = None
        resp = client.post("/", data={"phrase": "apple-sky-boat"})
    assert resp.status_code == 200
    assert b"didn&#39;t match" in resp.data or b"didn't match" in resp.data
    mock_db.fetch_invitee_by_phrase.assert_called_once_with("apple-sky-boat")


def test_self_register_honeypot_trips_silently(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases:
        resp = client.post(
            "/self-register",
            data={"honeypot": "I am a bot", "primary_name": "Alice"},
        )
    assert resp.status_code == 200
    mock_phrases.insert_with_unique_phrase.assert_not_called()
    mock_db.insert_self_invitee.assert_not_called()


def test_self_register_disabled_when_anonymous_phrase_unset(client):
    with patch("rsvp.routes_public.phrases") as mock_phrases:
        resp = client.post("/self-register", data={"primary_name": "Alice"})
    assert resp.status_code == 302
    mock_phrases.insert_with_unique_phrase.assert_not_called()


def test_self_register_requires_name(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    with patch("rsvp.routes_public.phrases") as mock_phrases:
        resp = client.post("/self-register", data={"primary_name": "  "})
    assert resp.status_code == 200
    assert b"tell us your name" in resp.data.lower()
    mock_phrases.insert_with_unique_phrase.assert_not_called()


def test_self_register_creates_invitee_with_origin_self(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    fake_id = uuid.uuid4()
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.invite_url.return_value = f"https://example.com/?code={fake_id}"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"

        resp = client.post(
            "/self-register",
            data={
                "primary_name": " Alice Example ",
                "email": "",
                "max_guests": "2",
                "rsvp_status": "Attending",
            },
        )

    assert resp.status_code == 200
    mock_phrases.insert_with_unique_phrase.assert_called_once_with(
        mock_db.insert_self_invitee, "Alice Example", "", 2
    )
    mock_db.update_rsvp.assert_called_once_with(fake_id, "Attending", "", "")
    assert b"apple-sky-boat" in resp.data
    assert b"data:image/png;base64," in resp.data
    assert b"attending" in resp.data.lower()


def test_self_register_requires_rsvp_status(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    with patch("rsvp.routes_public.phrases") as mock_phrases:
        resp = client.post("/self-register", data={"primary_name": "Alice"})
    assert resp.status_code == 200
    assert b"whether you" in resp.data.lower()
    mock_phrases.insert_with_unique_phrase.assert_not_called()

    with patch("rsvp.routes_public.phrases") as mock_phrases:
        resp = client.post(
            "/self-register",
            data={"primary_name": "Alice", "rsvp_status": "Maybe"},
        )
    assert resp.status_code == 200
    assert b"whether you" in resp.data.lower()
    mock_phrases.insert_with_unique_phrase.assert_not_called()


def test_self_register_records_notes_and_declined_status(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    fake_id = uuid.uuid4()
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.invite_url.return_value = "https://example.com/"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"

        resp = client.post(
            "/self-register",
            data={
                "primary_name": "Bob",
                "rsvp_status": "Declined",
                "comments": "  Can't make it, sorry!  ",
            },
        )

    assert resp.status_code == 200
    mock_db.update_rsvp.assert_called_once_with(fake_id, "Declined", "", "Can't make it, sorry!")
    assert b"declining" in resp.data.lower()


def test_self_register_truncates_comments(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    fake_id = uuid.uuid4()
    long_comment = "x" * 3000
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.invite_url.return_value = "https://example.com/"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"

        client.post(
            "/self-register",
            data={"primary_name": "Alice", "rsvp_status": "Attending", "comments": long_comment},
        )

    args, _ = mock_db.update_rsvp.call_args
    assert len(args[-1]) == 2000


def test_self_register_clamps_max_guests(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    fake_id = uuid.uuid4()
    with patch("rsvp.routes_public.db"), patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.invite_url.return_value = "https://example.com/"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"

        client.post(
            "/self-register",
            data={"primary_name": "Alice", "rsvp_status": "Attending", "max_guests": "999"},
        )
        args, _ = mock_phrases.insert_with_unique_phrase.call_args
        assert args[-1] == 20

        client.post(
            "/self-register",
            data={"primary_name": "Alice", "rsvp_status": "Attending", "max_guests": "-5"},
        )
        args, _ = mock_phrases.insert_with_unique_phrase.call_args
        assert args[-1] == 0

        client.post(
            "/self-register",
            data={"primary_name": "Alice", "rsvp_status": "Attending", "max_guests": "not-a-number"},
        )
        args, _ = mock_phrases.insert_with_unique_phrase.call_args
        assert args[-1] == 0


def test_self_register_truncates_long_name(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    fake_id = uuid.uuid4()
    long_name = "A" * 500
    with patch("rsvp.routes_public.db"), patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.invite_url.return_value = "https://example.com/"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"

        client.post(
            "/self-register",
            data={"primary_name": long_name, "rsvp_status": "Attending"},
        )
        args, _ = mock_phrases.insert_with_unique_phrase.call_args
        assert len(args[1]) == 200


def test_self_register_sends_confirmation_email_when_email_given(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    fake_id = uuid.uuid4()
    with patch("rsvp.routes_public.db"), patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.invite_url.return_value = "https://example.com/"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"

        client.post(
            "/self-register",
            data={"primary_name": "Alice", "rsvp_status": "Attending", "email": "alice@example.com"},
        )
        mock_services.send_self_registration_email.assert_called_once()

        mock_services.send_self_registration_email.reset_mock()
        client.post(
            "/self-register",
            data={"primary_name": "Bob", "rsvp_status": "Declined", "email": ""},
        )
        mock_services.send_self_registration_email.assert_not_called()


def test_self_register_email_failure_does_not_surface_to_guest(client, app):
    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    fake_id = uuid.uuid4()
    with patch("rsvp.routes_public.db"), patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.invite_url.return_value = "https://example.com/"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"
        mock_services.send_self_registration_email.side_effect = Exception("SES down")

        resp = client.post(
            "/self-register",
            data={"primary_name": "Alice", "rsvp_status": "Attending", "email": "alice@example.com"},
        )
    assert resp.status_code == 200
    assert b"apple-sky-boat" in resp.data


def test_no_public_qr_route_added(client):
    resp = client.get(f"/qr/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_admin_dashboard_flags_self_registered_rows(client, app):
    _login(client, app)
    self_registered_row = {
        "id": uuid.uuid4(),
        "primary_name": "Alice Example",
        "rsvp_status": "Pending",
        "max_guests": 2,
        "plus_one_details": None,
        "comments": None,
        "lookup_phrase": "apple-sky-boat",
        "email": None,
        "origin": "self",
        "reviewed": False,
    }
    counts = {
        "total": 1,
        "attending": 0,
        "declined": 0,
        "pending": 1,
        "with_comments": 0,
        "self_registered": 1,
        "pending_review": 1,
    }
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.fetch_all_invitees.return_value = [self_registered_row]
        mock_db.dashboard_counts.return_value = counts
        resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    assert b"self-registered, pending review" in resp.data
    assert b">1<" in resp.data
    assert b'action="/admin/confirm/' in resp.data


def test_admin_dashboard_hides_confirm_button_once_reviewed(client, app):
    _login(client, app)
    reviewed_row = {
        "id": uuid.uuid4(),
        "primary_name": "Bob Example",
        "rsvp_status": "Pending",
        "max_guests": 0,
        "plus_one_details": None,
        "comments": None,
        "lookup_phrase": "apple-sky-boat",
        "email": None,
        "origin": "self",
        "reviewed": True,
    }
    counts = {
        "total": 1,
        "attending": 0,
        "declined": 0,
        "pending": 1,
        "with_comments": 0,
        "self_registered": 1,
        "pending_review": 0,
    }
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.fetch_all_invitees.return_value = [reviewed_row]
        mock_db.dashboard_counts.return_value = counts
        resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    assert b"(self-registered)" in resp.data
    assert b"pending review" not in resp.data
    assert b'action="/admin/confirm/' not in resp.data


def test_confirm_invitee_marks_reviewed(client, app):
    _login(client, app)
    invitee_id = uuid.uuid4()
    with patch("rsvp.routes_admin.db") as mock_db:
        mock_db.mark_invitee_reviewed.return_value = True
        resp = client.post(f"/admin/confirm/{invitee_id}")
    assert resp.status_code == 302
    mock_db.mark_invitee_reviewed.assert_called_once_with(invitee_id)


def test_confirm_invitee_requires_login(client):
    resp = client.post(f"/admin/confirm/{uuid.uuid4()}")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("Location", "")


def test_confirm_invitee_rejects_bad_uuid(client, app):
    _login(client, app)
    with patch("rsvp.routes_admin.db") as mock_db:
        resp = client.post("/admin/confirm/not-a-uuid")
    assert resp.status_code == 302
    mock_db.mark_invitee_reviewed.assert_not_called()
