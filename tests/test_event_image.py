from unittest.mock import patch

from PIL import Image

from rsvp import services


def _make_png(path, width, height):
    Image.new("RGB", (width, height), color="red").save(path, format="PNG")


def test_event_image_bytes_resizes_when_too_wide(tmp_path):
    path = tmp_path / "wide.png"
    _make_png(path, 2000, 1000)
    data, mimetype = services.event_image_bytes(str(path), max_width=1200)
    assert mimetype == "image/png"
    with Image.open(services.io.BytesIO(data)) as img:
        assert img.width == 1200
        assert img.height == 600  # aspect ratio preserved


def test_event_image_bytes_leaves_small_images_alone(tmp_path):
    path = tmp_path / "small.png"
    _make_png(path, 400, 300)
    data, _ = services.event_image_bytes(str(path), max_width=1200)
    with Image.open(services.io.BytesIO(data)) as img:
        assert img.width == 400
        assert img.height == 300


def test_event_image_bytes_caches_across_calls(tmp_path):
    path = tmp_path / "cached.png"
    _make_png(path, 400, 300)
    first, _ = services.event_image_bytes(str(path))
    path.write_bytes(b"not a real image anymore")  # would blow up Image.open if re-read
    second, _ = services.event_image_bytes(str(path))
    assert first == second


def test_event_image_route_404s_when_unconfigured(client):
    resp = client.get("/event-image")
    assert resp.status_code == 404


def test_event_image_route_404s_when_file_missing(client, app, tmp_path):
    app.config["EVENT_DETAILS_IMAGE"] = "missing.png"
    with patch("rsvp.routes_public.ASSETS_DIR", str(tmp_path)):
        resp = client.get("/event-image")
    assert resp.status_code == 404


def test_event_image_route_serves_resized_image(client, app, tmp_path):
    _make_png(tmp_path / "invite.png", 2000, 1000)
    app.config["EVENT_DETAILS_IMAGE"] = "invite.png"
    with patch("rsvp.routes_public.ASSETS_DIR", str(tmp_path)):
        resp = client.get("/event-image")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.headers["Cache-Control"] == "public, max-age=86400"
    with Image.open(services.io.BytesIO(resp.data)) as img:
        assert img.width == 1200


def test_event_image_route_ignores_directory_traversal(client, app, tmp_path):
    app.config["EVENT_DETAILS_IMAGE"] = "../../etc/passwd"
    with patch("rsvp.routes_public.ASSETS_DIR", str(tmp_path)):
        resp = client.get("/event-image")
    assert resp.status_code == 404


def test_guest_pages_show_image_when_configured(client, app):
    app.config["EVENT_DETAILS_IMAGE"] = "invite.png"
    resp = client.get("/")
    assert b'class="event-image"' in resp.data


def test_guest_pages_hide_image_when_unconfigured(client):
    resp = client.get("/")
    assert b'class="event-image"' not in resp.data


def test_admin_pages_never_show_event_image(client, app):
    app.config["EVENT_DETAILS_IMAGE"] = "invite.png"
    resp = client.get("/admin/login")
    assert b'class="event-image"' not in resp.data
