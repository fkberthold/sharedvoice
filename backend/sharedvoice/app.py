"""SharedVoice FastAPI application factory.

Kept as a factory (`create_app`) so tests can build isolated instances and
future wiring (storage, routers) has a single composition point.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="SharedVoice", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
