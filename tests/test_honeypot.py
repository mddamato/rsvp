from unittest.mock import patch


def test_honeypot_on_rsvp_never_touches_db(client):
    with patch("rsvp.routes_public.db") as mock_db:
        resp = client.post(
            "/rsvp",
            data={
                "honeypot": "I am a bot",
                "invitee_id": "5f0c9c1e-0000-0000-0000-000000000000",
                "rsvp_status": "Attending",
            },
        )
    assert resp.status_code in (200, 302)
    mock_db.update_rsvp.assert_not_called()
    mock_db.fetch_invitee_by_id.assert_not_called()


def test_honeypot_on_phrase_lookup_never_queries(client):
    with patch("rsvp.routes_public.db") as mock_db:
        resp = client.post("/", data={"honeypot": "x", "phrase": "a-b-c"})
    assert resp.status_code == 200
    mock_db.fetch_invitee_by_phrase.assert_not_called()


def test_honeypot_on_recover_sends_nothing(client):
    with patch("rsvp.routes_public.db") as mock_db, patch(
        "rsvp.routes_public.services"
    ) as mock_services:
        resp = client.post(
            "/recover", data={"honeypot": "x", "email": "a@b.com"}
        )
    assert resp.status_code == 200
    mock_db.fetch_invitee_by_email.assert_not_called()
    mock_services.send_recovery_email.assert_not_called()
