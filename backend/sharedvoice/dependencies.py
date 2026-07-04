from __future__ import annotations
from fastapi import Depends, HTTPException, Request
from . import users
from .storage.db import connect
from .users import User

def current_user(request: Request) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="not authenticated")
    conn = connect(request.app.state.db_path)
    try:
        user = users.get_user_by_id(conn, user_id)
    finally:
        conn.close()
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user

def require_curator(user: User = Depends(current_user)) -> User:
    if not user.is_curator:
        raise HTTPException(status_code=403, detail="curator only")
    return user
