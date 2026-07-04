"""Curator-only root-recording upload (sv-lds.7).

A curator uploads a source clip for an affirmation; it is decoded, downmixed,
and resampled to the canonical 48 kHz mono format, stored as a blob, and
recorded as that affirmation's root ``Recording``.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from .. import models
from ..audio.ingest import InvalidAudioError, encode_wav, resample_to_48k_mono
from ..dependencies import require_curator
from ..storage.db import connect

router = APIRouter(dependencies=[Depends(require_curator)])


@router.post("/affirmations/{affirmation_id}/root", status_code=201)
async def upload_root(affirmation_id: str, request: Request, file: UploadFile) -> dict:
    conn = connect(request.app.state.db_path)
    try:
        affirmation = models.get_affirmation(conn, affirmation_id)
        if affirmation is None:
            raise HTTPException(status_code=404, detail="affirmation not found")

        raw = await file.read()
        try:
            samples, sample_rate, duration = resample_to_48k_mono(raw)
        except InvalidAudioError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        recording = models.Recording(
            id=uuid.uuid4().hex,
            affirmation_id=affirmation_id,
            audio_path=f"roots/{affirmation_id}.wav",
            sample_rate=sample_rate,
            duration=duration,
        )
        request.app.state.storage.put(recording.audio_path, encode_wav(samples, sample_rate))
        models.add_recording(conn, recording)
        models.set_root_recording(conn, affirmation_id, recording.id)
    finally:
        conn.close()

    return asdict(recording)
