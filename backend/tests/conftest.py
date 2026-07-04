"""Suite-wide test fixtures.

``create_app`` fails fast when ``SHAREDVOICE_SECRET_KEY`` is unset (sv-dkl.2).
This autouse fixture supplies that key (plus the join code) for every test so
the pre-existing suite keeps constructing apps without env boilerplate. Tests
that exercise the fail-fast path delete the key themselves via monkeypatch.
"""

import pytest


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setenv("SHAREDVOICE_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SHAREDVOICE_JOIN_CODE", "test-join-code")
