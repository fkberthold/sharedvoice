"""Auth endpoints — register, login, logout, me (sv-dkl.3)."""

from __future__ import annotations

import hmac
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .. import security, users
from ..dependencies import current_user
from ..storage.db import connect
from ..users import User

router = APIRouter(prefix="/auth")

# Fixed dummy bcrypt hash used to pay the same verify_password cost on the
# user-not-found login path as on the wrong-password path, so an unknown
# username can't be distinguished from a wrong password by response timing
# (sv-9wi). Precomputed once (bcrypt.hashpw of a fixed dummy string) so it
# doesn't need to be recomputed per request; the plaintext it corresponds to
# is never accepted by any real user, so this is not a usable credential.
_DUMMY_PASSWORD_HASH = "$2b$12$QCkNrQVW3Lvc1yFM8ZzIiO0DxoYp5T7ognl5zISOIICtXNcKL/dK."


class RegisterBody(BaseModel):
    join_code: str
    username: str
    display_name: str
    password: str


class LoginBody(BaseModel):
    username: str
    password: str


def _public(u: User) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "is_curator": u.is_curator}


@router.post("/register", status_code=201)
def register(body: RegisterBody, request: Request) -> dict:
    configured = request.app.state.join_code or ""
    if not hmac.compare_digest(body.join_code, configured):
        raise HTTPException(status_code=403, detail="invalid join code")
    conn = connect(request.app.state.db_path)
    try:
        if users.get_user_by_username(conn, body.username) is not None:
            raise HTTPException(status_code=409, detail="username taken")
        is_curator = users.count_users(conn) == 0
        user = User(
            id=uuid.uuid4().hex,
            username=body.username,
            display_name=body.display_name,
            password_hash=security.hash_password(body.password),
            is_curator=is_curator,
        )
        users.create_user(conn, user)
    finally:
        conn.close()
    request.session["user_id"] = user.id
    return _public(user)


@router.post("/login")
def login(body: LoginBody, request: Request) -> dict:
    conn = connect(request.app.state.db_path)
    try:
        user = users.get_user_by_username(conn, body.username)
    finally:
        conn.close()
    if user is None:
        # Still pay the verify_password cost against a fixed dummy hash so
        # this path takes the same time as the wrong-password path below —
        # otherwise response latency alone would leak whether a username
        # exists, even though the response body is already identical.
        security.verify_password(body.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="invalid credentials")
    if not security.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    request.session["user_id"] = user.id
    return _public(user)


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return _public(user)
