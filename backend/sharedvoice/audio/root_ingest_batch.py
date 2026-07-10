"""Batch root-recording ingest from a directory of clip files (sv-lds.20.2).

``ingest_root_clips`` is the batch sibling of ``routers/roots.py``'s
per-upload ``upload_root``: instead of reading one ``UploadFile`` at a time
over HTTP, it walks a directory of clip files on disk, matches each one to
an existing affirmation by filename stem, and runs it through the SAME
``resample_to_48k_mono`` + ``encode_wav`` pipeline used by the curator
upload path.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from .. import models
from .ingest import encode_wav, resample_to_48k_mono


def ingest_root_clips(conn, storage, clips_dir) -> list[str]:
    """Ingest every clip in `clips_dir` whose filename stem matches an
    existing affirmation id, storing each as that affirmation's root
    recording. Files whose stem does not match any affirmation are silently
    skipped. Returns the sorted list of affirmation ids successfully
    ingested.
    """
    ingested: list[str] = []

    for path in sorted(Path(clips_dir).iterdir()):
        if not path.is_file():
            continue

        affirmation_id = path.stem
        affirmation = models.get_affirmation(conn, affirmation_id)
        if affirmation is None:
            continue

        samples, sample_rate, duration = resample_to_48k_mono(str(path))

        recording = models.Recording(
            id=uuid.uuid4().hex,
            affirmation_id=affirmation_id,
            audio_path=f"roots/{affirmation_id}.wav",
            sample_rate=sample_rate,
            duration=duration,
        )
        storage.put(recording.audio_path, encode_wav(samples, sample_rate))
        models.add_recording(conn, recording)
        models.set_root_recording(conn, affirmation_id, recording.id)

        ingested.append(affirmation_id)

    return sorted(ingested)
