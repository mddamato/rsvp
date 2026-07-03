import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import pytest
from rsvp import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "DOMAIN_NAME": "example.com",
            "HTPASSWD_PATH": str(tmp_path / "htpasswd"),
            "SESSION_COOKIE_SECURE": False,
        }
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()
