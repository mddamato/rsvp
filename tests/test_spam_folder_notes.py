import uuid
from unittest.mock import patch

SPAM_TEXT = b"spam"


def test_recover_confirmation_mentions_spam_folder(client):
    with patch("rsvp.routes_public.db") as mock_db:
        mock_db.fetch_invitee_by_email.return_value = None
        resp = client.post("/recover", data={"email": "guest@example.com"})
    assert resp.status_code == 200
    assert SPAM_TEXT in resp.data.lower()


def test_self_register_confirm_mentions_spam_folder_when_emailed(client, app):
    from rsvp import services

    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    token = services.register_token(app.config["SECRET_KEY"])
    fake_id = uuid.uuid4()
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.register_token.side_effect = services.register_token
        mock_services.invite_url.return_value = "https://example.com/"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"
        resp = client.post(
            "/self-register",
            data={
                "primary_name": "Alice",
                "rsvp_status": "Attending",
                "email": "alice@example.com",
                "t": token,
            },
        )
    assert resp.status_code == 200
    assert SPAM_TEXT in resp.data.lower()


def test_self_register_confirm_omits_spam_note_without_email(client, app):
    from rsvp import services

    app.config["ANONYMOUS_PHRASE"] = "Tonys third birthday"
    token = services.register_token(app.config["SECRET_KEY"])
    fake_id = uuid.uuid4()
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.phrases"
    ) as mock_phrases, patch("rsvp.routes_public.services") as mock_services:
        mock_phrases.insert_with_unique_phrase.return_value = (fake_id, "apple-sky-boat")
        mock_services.register_token.side_effect = services.register_token
        mock_services.invite_url.return_value = "https://example.com/"
        mock_services.qr_png_bytes.return_value = b"fake-png-bytes"
        resp = client.post(
            "/self-register",
            data={"primary_name": "Alice", "rsvp_status": "Attending", "t": token},
        )
    assert resp.status_code == 200
    assert SPAM_TEXT not in resp.data.lower()


def test_submit_rsvp_redirects_with_emailed_flag_when_email_given(client, app):
    invitee = {
        "id": uuid.uuid4(),
        "primary_name": "Alice",
        "rsvp_status": "Pending",
        "max_guests": 0,
        "plus_one_details": None,
        "comments": None,
        "lookup_phrase": "apple-sky-boat",
        "email": None,
    }
    with patch("rsvp.routes_public.db") as mock_db, patch("rsvp.routes_public.services"):
        mock_db.fetch_invitee_by_id.return_value = invitee
        resp = client.post(
            "/rsvp",
            data={
                "invitee_id": str(invitee["id"]),
                "rsvp_status": "Attending",
                "email": "guest@example.com",
            },
        )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/thanks?emailed=1"


def test_submit_rsvp_redirects_without_emailed_flag_when_no_email(client, app):
    invitee = {
        "id": uuid.uuid4(),
        "primary_name": "Alice",
        "rsvp_status": "Pending",
        "max_guests": 0,
        "plus_one_details": None,
        "comments": None,
        "lookup_phrase": "apple-sky-boat",
        "email": None,
    }
    with patch("rsvp.routes_public.db") as mock_db:
        mock_db.fetch_invitee_by_id.return_value = invitee
        resp = client.post(
            "/rsvp",
            data={"invitee_id": str(invitee["id"]), "rsvp_status": "Declined"},
        )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/thanks"


def test_thanks_page_shows_spam_note_when_emailed(client):
    resp = client.get("/thanks?emailed=1")
    assert resp.status_code == 200
    assert SPAM_TEXT in resp.data.lower()


def test_thanks_page_omits_spam_note_when_not_emailed(client):
    resp = client.get("/thanks")
    assert resp.status_code == 200
    assert SPAM_TEXT not in resp.data.lower()
