"""Password hashing — bcrypt-backed, salted per call.

Thin wrapper around ``bcrypt``: ``hash_password`` encodes/decodes at the
str boundary so callers (and the DAO) never touch bytes or the bcrypt
module directly.
"""

from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
