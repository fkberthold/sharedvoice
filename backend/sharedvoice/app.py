"""SharedVoice FastAPI application factory.

`create_app` wires the SQLite metadata DB (seeded with the affirmation
corpus) and the audio blob store into the app, then mounts the routers.
Pass explicit ``db_path`` / ``storage_root`` in tests; production uses the
``var/`` defaults (overridable via SHAREDVOICE_DB / SHAREDVOICE_BLOBS).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from . import corpus, models, users
from .routers import affirmations as affirmations_router
from .routers import auth as auth_router
from .storage import db
from .storage.local import LocalBlobStore

DEFAULT_DB = Path(os.environ.get("SHAREDVOICE_DB", "var/sharedvoice.db"))
DEFAULT_BLOBS = Path(os.environ.get("SHAREDVOICE_BLOBS", "var/blobs"))


def create_app(
    db_path: Path | str | None = None,
    storage_root: Path | str | None = None,
) -> FastAPI:
    secret_key = os.environ.get("SHAREDVOICE_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SHAREDVOICE_SECRET_KEY must be set")

    db_path = Path(db_path) if db_path is not None else DEFAULT_DB
    storage_root = Path(storage_root) if storage_root is not None else DEFAULT_BLOBS
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = db.connect(db_path)
    models.init_schema(conn)
    users.init_user_schema(conn)
    corpus.seed_affirmations(conn)
    conn.close()

    app = FastAPI(title="SharedVoice", version="0.1.0")
    app.add_middleware(SessionMiddleware, secret_key=secret_key)
    app.state.db_path = db_path
    app.state.storage = LocalBlobStore(storage_root)
    app.state.join_code = os.environ.get("SHAREDVOICE_JOIN_CODE")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(affirmations_router.router)
    app.include_router(auth_router.router)
    return app
