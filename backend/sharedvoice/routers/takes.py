"""Member-accessible take upload (sv-lds.14).

Any logged-in sangha member (not curator-only, unlike root upload — sv-lds.7)
uploads a recitation-along recording for an affirmation; it is decoded,
downmixed, and resampled to the canonical 48 kHz mono format via the same
``sharedvoice.audio.ingest`` pipeline root upload uses, stored as a blob, and
recorded as a ``Take`` row stamped with the uploader's identity.

Alignment is intentionally left ``None`` here — the real aligner is
sv-lds.15, still blocked/future work.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from .. import models
from ..audio.ingest import InvalidAudioError, encode_wav, resample_to_48k_mono
from ..dependencies import current_user
from ..storage.db import connect
from ..takes import Take, create_take
from ..users import User

router = APIRouter()


@router.post("/affirmations/{affirmation_id}/takes", status_code=201)
async def upload_take(
    affirmation_id: str,
    request: Request,
    file: UploadFile,
    user: User = Depends(current_user),
) -> dict:
    conn = connect(request.app.state.db_path)
    try:
        affirmation = models.get_affirmation(conn, affirmation_id)
        if affirmation is None:
            raise HTTPException(status_code=404, detail="affirmation not found")

        raw = await file.read()
        try:
            samples, sample_rate, _duration = resample_to_48k_mono(raw)
        except InvalidAudioError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        take_id = uuid.uuid4().hex
        take = Take(
            id=take_id,
            affirmation_id=affirmation_id,
            user_id=user.id,
            contributor_name=user.display_name,
            audio_path=f"takes/{affirmation_id}/{take_id}.wav",
            alignment=None,
        )
        request.app.state.storage.put(take.audio_path, encode_wav(samples, sample_rate))
        create_take(conn, take)
    finally:
        conn.close()

    return asdict(take)
