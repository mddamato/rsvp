import uuid
from unittest.mock import patch


def _invitee(email=None, max_guests=0):
    return {
        "id": uuid.uuid4(),
        "primary_name": "Alice Example",
        "rsvp_status": "Pending",
        "max_guests": max_guests,
        "plus_one_details": None,
        "comments": None,
        "lookup_phrase": "apple-sky-boat",
        "email": email,
    }


def test_submit_rsvp_sends_confirmation_when_email_submitted(client, app):
    # rsvp_form.html pre-fills the email field with the invitee's
    # current email, so a normal browser submission always resends it
    # even if the guest didn't touch that field -- simulated here by
    # including it in the POST data explicitly.
    invitee = _invitee(email="guest@example.com")
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.services"
    ) as mock_services:
        mock_db.fetch_invitee_by_id.return_value = invitee
        mock_services.invite_url.return_value = "https://example.com/?code=1"
        resp = client.post(
            "/rsvp",
            data={
                "invitee_id": str(invitee["id"]),
                "rsvp_status": "Attending",
                "email": "guest@example.com",
            },
        )
    assert resp.status_code == 302
    mock_db.update_rsvp.assert_called_once_with(
        invitee["id"], "Attending", "[]", "", "guest@example.com"
    )
    mock_services.send_rsvp_confirmation_email.assert_called_once()
    args = mock_services.send_rsvp_confirmation_email.call_args.args
    assert args[1] == "guest@example.com"
    assert args[4] == "Attending"


def test_submit_rsvp_skips_email_when_none_submitted(client, app):
    invitee = _invitee(email=None)
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.services"
    ) as mock_services:
        mock_db.fetch_invitee_by_id.return_value = invitee
        resp = client.post(
            "/rsvp",
            data={"invitee_id": str(invitee["id"]), "rsvp_status": "Declined"},
        )
    assert resp.status_code == 302
    mock_services.send_rsvp_confirmation_email.assert_not_called()
    mock_db.update_rsvp.assert_called_once_with(invitee["id"], "Declined", "[]", "", "")


def test_submit_rsvp_sends_confirmation_when_email_added_for_first_time(client, app):
    # An admin-added guest with no email on file adds one while
    # RSVPing -- should get a confirmation immediately, not just on
    # some future submission.
    invitee = _invitee(email=None)
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.services"
    ) as mock_services:
        mock_db.fetch_invitee_by_id.return_value = invitee
        resp = client.post(
            "/rsvp",
            data={
                "invitee_id": str(invitee["id"]),
                "rsvp_status": "Attending",
                "email": "new@example.com",
            },
        )
    assert resp.status_code == 302
    mock_services.send_rsvp_confirmation_email.assert_called_once()
    args = mock_services.send_rsvp_confirmation_email.call_args.args
    assert args[1] == "new@example.com"


def test_submit_rsvp_email_failure_does_not_break_rsvp(client, app):
    invitee = _invitee(email="guest@example.com")
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.services"
    ) as mock_services:
        mock_db.fetch_invitee_by_id.return_value = invitee
        mock_services.send_rsvp_confirmation_email.side_effect = Exception("SES down")
        resp = client.post(
            "/rsvp",
            data={
                "invitee_id": str(invitee["id"]),
                "rsvp_status": "Attending",
                "email": "guest@example.com",
            },
        )
    assert resp.status_code == 302
    mock_db.update_rsvp.assert_called_once()


def test_submit_rsvp_passes_guests_and_comments_to_email(client, app):
    invitee = _invitee(email="guest@example.com", max_guests=2)
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.services"
    ) as mock_services:
        mock_db.fetch_invitee_by_id.return_value = invitee
        resp = client.post(
            "/rsvp",
            data={
                "invitee_id": str(invitee["id"]),
                "rsvp_status": "Attending",
                "email": "guest@example.com",
                "guest_name_1": "Bob",
                "comments": "no nuts",
            },
        )
    assert resp.status_code == 302
    args = mock_services.send_rsvp_confirmation_email.call_args.args
    assert args[5] == [{"name": "Bob", "child": False}]
    assert args[6] == "no nuts"
