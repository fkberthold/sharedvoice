"""Read endpoints for the affirmation corpus + root-recording serving."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response

from .. import models, takes
from ..audio.align import align_offset
from ..audio.ingest import encode_wav, resample_to_48k_mono
from ..audio.mix import mix_tracks
from ..dependencies import current_user, require_curator
from ..storage.db import connect

router = APIRouter(dependencies=[Depends(current_user)])

# Generous latency window for this GLOBAL (whole-recitation) offset search.
# There's no scheduling hint to center the search on here (unlike a future
# per-phrase aligner, sv-lds.18, which will have one) -- a contributor's
# overall delay before beginning to recite along (headphone playback start,
# mic/app spin-up, plain reaction time) can plausibly run a few seconds.
# 3s is generous enough to cover that startup latency while staying a small
# fraction of a full affirmation's recitation length (the corpus's
# affirmations run well past 10s), so the search window stays clear of a
# later repeated line-opening -- the anaphora bug the windowed search in
# audio/align.py guards against.
_MIX_MAX_OFFSET_SECONDS = 3.0


def _shift_into_alignment(samples: np.ndarray, offset_seconds: float, sr: int) -> np.ndarray:
    """Shift `samples` so its content lines up with the reference timeline,
    given `offset_seconds` from `align_offset` (sign convention:
    ``candidate[t] ~= reference[t - offset]``). A positive offset means the
    candidate is delayed, so aligning it means pulling it EARLIER by that
    many seconds; a negative offset means it leads, so aligning it means
    pushing it LATER. Same length in/out, zero-padded at the freed edge --
    conceptually mirrors ``audio.mix._shift_samples``, kept as a separate
    helper here since that one is private to the mix module.
    """
    shift_samples = int(round(offset_seconds * sr))
    if shift_samples == 0:
        return samples.astype(np.float32, copy=True)

    aligned = np.zeros_like(samples)
    n = len(samples)
    if shift_samples > 0:
        # candidate delayed -- advance it earlier by shift_samples
        if shift_samples < n:
            aligned[: n - shift_samples] = samples[shift_samples:]
    else:
        # candidate leads -- delay it by -shift_samples
        delay = -shift_samples
        if delay < n:
            aligned[delay:] = samples[: n - delay]
    return aligned


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


@router.get("/affirmations/{affirmation_id}/mix")
def get_mix(
    affirmation_id: str, request: Request, _curator=Depends(require_curator)
) -> Response:
    """Sum-mix the affirmation's root plus every uploaded take, each take
    shifted into alignment with the root via a global-offset search
    (``audio.align.align_offset``), and return the mixed WAV for download.

    Curator-only (per the build brief -- downloading a mix is a curator
    action). Mixes ALL takes unconditionally; there's no voice-selection UI
    yet (sv-lds.19). Zero takes is a valid "mix of one": the root alone,
    passed through the same encode/limiter pipeline as any other mix.
    """
    conn = connect(request.app.state.db_path)
    try:
        affirmation = models.get_affirmation(conn, affirmation_id)
        if affirmation is None:
            raise HTTPException(status_code=404, detail="affirmation not found")

        recording = (
            models.get_recording(conn, affirmation.root_recording_id)
            if affirmation.root_recording_id
            else None
        )
        if recording is None:
            raise HTTPException(status_code=404, detail="no root recording")

        contributor_takes = takes.list_takes_by_affirmation(conn, affirmation_id)
    finally:
        conn.close()

    storage = request.app.state.storage
    root_samples, sr, _duration = resample_to_48k_mono(storage.get(recording.audio_path))

    tracks = [root_samples]
    for take in contributor_takes:
        candidate_samples, _sr, _dur = resample_to_48k_mono(storage.get(take.audio_path))
        offset = align_offset(
            root_samples,
            candidate_samples,
            sr,
            expected_offset=0.0,
            max_offset_seconds=_MIX_MAX_OFFSET_SECONDS,
        )
        tracks.append(_shift_into_alignment(candidate_samples, offset, sr))

    mixed = mix_tracks(tracks, sr)
    wav_bytes = encode_wav(mixed, sr)

    headers = {"Content-Disposition": f'attachment; filename="{affirmation_id}-mix.wav"'}
    return Response(content=wav_bytes, media_type="audio/wav", headers=headers)
