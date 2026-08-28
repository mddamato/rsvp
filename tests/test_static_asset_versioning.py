import re


def test_style_and_enhance_js_urls_carry_a_cache_busting_version(client):
    """Every page extends base.html, which loads style.css and
    enhance.js through static_url() instead of a bare url_for('static',
    ...) -- otherwise a browser that already cached an old enhance.js
    keeps running it after a deploy ships new behavior (e.g. the admin
    dashboard's "select all" checkbox), since the URL never changes."""
    resp = client.get("/")
    body = resp.data.decode()
    assert re.search(r'/static/style\.css\?v=\d+', body)
    assert re.search(r'/static/enhance\.js\?v=\d+', body)
