"""QR code generation (in memory, never touches disk) and SES email."""
import hashlib
import hmac
import io

import qrcode
from PIL import Image

EVENT_IMAGE_MAX_WIDTH = 1200  # plenty sharp at the card's ~34rem display width, even on 2x displays

_event_image_cache = {}


def event_image_token(secret_key):
    """Short token proving a request for /event-image originated from
    a page the visitor could only reach by already knowing a valid
    passcode/link (or the self-registration phrase) -- the same
    bearer-token model as the personal RSVP link itself, applied to
    the image URL too, so a bot scanning the site blind can't fetch it
    without ever supplying a passcode. Derived from SECRET_KEY (not
    per-guest, not time-limited) so every gunicorn worker process
    computes the identical value with no shared state needed."""
    return hmac.new(secret_key.encode(), b"event-image", hashlib.sha256).hexdigest()[:16]


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


def event_image_bytes(path, max_width=EVENT_IMAGE_MAX_WIDTH):
    """Read, downsize if needed, and return (bytes, mimetype) for the
    configured invitation image. Resized once and cached in memory for
    the process lifetime -- the source file doesn't change without an
    app restart, same as any other config change. Raises OSError (via
    Image.open) if the file is missing or unreadable; callers turn
    that into a 404."""
    if path in _event_image_cache:
        return _event_image_cache[path]

    with Image.open(path) as img:
        img.load()
        fmt = img.format
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, round(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        save_kwargs = {"optimize": True}
        if fmt == "JPEG":
            save_kwargs["quality"] = 85
        img.save(buf, format=fmt, **save_kwargs)
        result = (buf.getvalue(), Image.MIME.get(fmt, "application/octet-stream"))

    _event_image_cache[path] = result
    return result


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


def send_self_registration_email(region, sender, recipient, url, phrase):
    """Send the self-registration confirmation email via SES, mirroring
    send_recovery_email. Imported lazily so tests and local dev don't
    need boto3 credentials."""
    import boto3

    client = boto3.client("ses", region_name=region)
    body = (
        "Hi,\n\n"
        "Thanks for signing up! Here is your invitation link:\n"
        f"{url}\n\n"
        f"Your passcode, if you prefer to type it in: {phrase}\n\n"
        "Hang onto this email -- you'll need your link or passcode to "
        "RSVP or change your answer later.\n\n"
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
