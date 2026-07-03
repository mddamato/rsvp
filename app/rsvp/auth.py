"""Admin authentication against a .htpasswd file on disk."""
from functools import wraps

from flask import current_app, redirect, session, url_for
from passlib.apache import HtpasswdFile


def verify_credentials(username, password, htpasswd_path=None):
    path = htpasswd_path or current_app.config["HTPASSWD_PATH"]
    try:
        ht = HtpasswdFile(path)
    except FileNotFoundError:
        return False
    result = ht.check_password(username, password)
    # check_password returns None for unknown user, False for bad password
    return result is True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapped
