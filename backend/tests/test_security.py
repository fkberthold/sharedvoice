"""Contract: password hashing is bcrypt, salted, and verifiable.

Pins ``hash_password`` / ``verify_password``: the hash is a str that is not
the plaintext, the same password hashes to different strings each call
(salted), and verification is true iff the password matches its hash. RED
until security.py exists.
"""

from sharedvoice.security import hash_password, verify_password


def test_hash_password_returns_str_not_plaintext():
    pw = "correct horse battery staple"
    h = hash_password(pw)
    assert isinstance(h, str)
    assert h != pw


def test_verify_password_matches_its_hash():
    pw = "correct horse battery staple"
    assert verify_password(pw, hash_password(pw)) is True


def test_verify_password_rejects_wrong_password():
    pw = "correct horse battery staple"
    assert verify_password("wrong" + pw, hash_password(pw)) is False


def test_hash_password_is_salted():
    pw = "correct horse battery staple"
    assert hash_password(pw) != hash_password(pw)
