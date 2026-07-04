"""Read endpoints for the affirmation corpus + root-recording serving."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .. import models
from ..dependencies import current_user
from ..storage.db import connect

router = APIRouter(dependencies=[Depends(current_user)])


@router.get("/affirmations")
def list_affirmations(request: Request) -> list[dict]:
    conn = connect(request.app.state.db_path)
    try:
        return [asdict(a) for a in models.list_affirmations(conn)]
    finally:
        conn.close()


@router.get("/affirmations/{affirmation_id}")
def get_affirmation(affirmation_id: str, request: Request) -> dict:
    conn = connect(request.app.state.db_path)
    try:
        affirmation = models.get_affirmation(conn, affirmation_id)
    finally:
        conn.close()
    if affirmation is None:
        raise HTTPException(status_code=404, detail="affirmation not found")
    return asdict(affirmation)


@router.get("/affirmations/{affirmation_id}/root")
def get_root(affirmation_id: str, request: Request) -> FileResponse:
    conn = connect(request.app.state.db_path)
    try:
        affirmation = models.get_affirmation(conn, affirmation_id)
        recording = (
            models.get_recording(conn, affirmation.root_recording_id)
            if affirmation and affirmation.root_recording_id
            else None
        )
    finally:
        conn.close()
    if recording is None:
        raise HTTPException(status_code=404, detail="no root recording")
    storage = request.app.state.storage
    return FileResponse(storage.path(recording.audio_path), media_type="audio/wav")
