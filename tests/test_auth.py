from passlib.apache import HtpasswdFile
from rsvp import auth


def test_htpasswd_roundtrip(tmp_path):
    path = str(tmp_path / "htpasswd")
    ht = HtpasswdFile(path, new=True)
    ht.set_password("host", "correct horse battery")
    ht.save()

    assert auth.verify_credentials("host", "correct horse battery", path)
    assert not auth.verify_credentials("host", "wrong", path)
    assert not auth.verify_credentials("nobody", "correct horse battery", path)


def test_missing_file_denies(tmp_path):
    assert not auth.verify_credentials("host", "pw", str(tmp_path / "nope"))


def test_admin_routes_require_login(client):
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]
