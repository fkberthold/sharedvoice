"""Password hashing — bcrypt-backed, salted per call.

Thin wrapper around ``bcrypt``: ``hash_password`` encodes/decodes at the
str boundary so callers (and the DAO) never touch bytes or the bcrypt
module directly.

``SHAREDVOICE_BCRYPT_ROUNDS`` overrides bcrypt's work factor (cost). Unset,
``bcrypt.gensalt()`` uses bcrypt's own default (12) — production behavior is
unchanged. Tests set it low (sv-1x1) since real bcrypt hashing at the
default cost is the dominant cost of the auth test suite.
"""

from __future__ import annotations

import os

import bcrypt

_ROUNDS_ENV_VAR = "SHAREDVOICE_BCRYPT_ROUNDS"


def hash_password(password: str) -> str:
    rounds = os.environ.get(_ROUNDS_ENV_VAR)
    salt = bcrypt.gensalt(rounds=int(rounds)) if rounds else bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
