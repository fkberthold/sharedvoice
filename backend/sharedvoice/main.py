"""Uvicorn entrypoint: `uvicorn sharedvoice.main:app` (run from backend/)."""

from sharedvoice.app import create_app

app = create_app()
