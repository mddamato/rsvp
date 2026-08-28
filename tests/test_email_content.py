from unittest.mock import patch

from rsvp import services

CFG = {
    "AWS_REGION": "us-east-1",
    "SES_SENDER_EMAIL": "host@example.com",
    "EVENT_TITLE": "Tony's Birthday!",
    "EVENT_SUBHEADING": "Saturday, October 17",
    "EVENT_DETAILS": "123 Party Ave",
    "EVENT_CLOSING": "- The Family",
}


def test_event_details_block_includes_all_set_fields():
    block = services._event_details_block(CFG)
    assert "Tony's Birthday!" in block
    assert "Saturday, October 17" in block
    assert "123 Party Ave" in block
    assert "- The Family" in block


def test_event_details_block_omits_unset_fields():
    block = services._event_details_block({"EVENT_TITLE": "Our Celebration"})
    assert block == "Our Celebration"


def test_status_word():
    assert services._status_word("Attending") == "Attending"
    assert services._status_word("Declined") == "Declining"


def test_send_recovery_email_content():
    with patch("boto3.client") as mock_client:
        services.send_recovery_email(CFG, "guest@example.com", "https://x/?code=1", "apple-sky-boat")
    mock_client.assert_called_once_with("ses", region_name="us-east-1")
    call = mock_client.return_value.send_email.call_args.kwargs
    assert call["Source"] == "host@example.com"
    assert call["Destination"] == {"ToAddresses": ["guest@example.com"]}
    body = call["Message"]["Body"]["Text"]["Data"]
    assert "https://x/?code=1" in body
    assert "apple-sky-boat" in body
    assert "Tony's Birthday!" in body
    assert "123 Party Ave" in body


def test_send_self_registration_email_mentions_status():
    with patch("boto3.client") as mock_client:
        services.send_self_registration_email(
            CFG, "guest@example.com", "https://x/?code=1", "apple-sky-boat", "Declined"
        )
    body = mock_client.return_value.send_email.call_args.kwargs["Message"]["Body"]["Text"]["Data"]
    assert "Declining" in body
    assert "Tony's Birthday!" in body


def test_send_rsvp_confirmation_email_attending_with_guests_and_notes():
    with patch("boto3.client") as mock_client:
        services.send_rsvp_confirmation_email(
            CFG,
            "guest@example.com",
            "https://x/?code=1",
            "apple-sky-boat",
            "Attending",
            guest_list=[{"name": "Bob Smith", "child": True}, {"name": "Sue Smith", "child": False}],
            comments="No nuts please",
        )
    call = mock_client.return_value.send_email.call_args.kwargs
    assert call["Message"]["Subject"]["Data"] == "Your RSVP confirmation"
    body = call["Message"]["Body"]["Text"]["Data"]
    assert "Attending" in body
    assert "Bob Smith (child), Sue Smith" in body
    assert "No nuts please" in body
    assert "See you there!" in body
    assert "Tony's Birthday!" in body
    assert "123 Party Ave" in body


def test_send_rsvp_confirmation_email_declined_without_guests_or_notes():
    with patch("boto3.client") as mock_client:
        services.send_rsvp_confirmation_email(
            CFG, "guest@example.com", "https://x/?code=1", "apple-sky-boat", "Declined"
        )
    body = mock_client.return_value.send_email.call_args.kwargs["Message"]["Body"]["Text"]["Data"]
    assert "Declining" in body
    assert "Bringing:" not in body
    assert "Your note:" not in body
    assert "Thanks for letting us know." in body
