"""QR code generation (in memory, never touches disk) and SES email."""
import io

import qrcode


def qr_png_bytes(url):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def invite_url(domain, invitee_id):
    return f"https://{domain}/?code={invitee_id}"


def send_recovery_email(region, sender, recipient, url, phrase):
    """Send the Tier-3 recovery email via SES. Imported lazily so tests
    and local dev don't need boto3 credentials."""
    import boto3

    client = boto3.client("ses", region_name=region)
    body = (
        "Hi,\n\n"
        "Here is your invitation link:\n"
        f"{url}\n\n"
        f"Your passcode, if you prefer to type it in: {phrase}\n\n"
        "See you there!"
    )
    client.send_email(
        Source=sender,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": "Your invitation link"},
            "Body": {"Text": {"Data": body}},
        },
    )
