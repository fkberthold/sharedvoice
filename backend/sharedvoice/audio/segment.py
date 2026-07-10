"""Pure ffmpeg-backed source-recording splitter (sv-lds.20.1).

``cut_segments`` carves ONE long source recording into per-affirmation clips
using cut points shaped like ``data/refuge_split.yaml`` (each entry
``{"id": str, "start": float}``, seconds from the top of the file, ORDERED
ascending by start). Segment ``i`` spans ``[start_i, start_{i+1})``; the LAST
segment spans ``[start_last, end-of-file]``. Each clip is written to
``output_dir/{id}.wav`` as 16-bit PCM WAV via an ffmpeg subprocess call.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


def cut_segments(
    source_path: str | Path, segments: list[dict], output_dir: str | Path
) -> dict[str, Path]:
    """Cut `source_path` into one clip per entry in `segments` (each entry
    {"id": str, "start": float}, seconds from the top of the file, ORDERED
    ascending by start). Segment i spans [start_i, start_{i+1}); the LAST
    segment spans [start_last, end-of-file]. Writes each clip to
    `output_dir/{id}.wav` (16-bit PCM WAV) via ffmpeg. Returns
    {id: output_path} for every segment written.
    """
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Path] = {}

    for i, segment in enumerate(segments):
        seg_id = segment["id"]
        start = segment["start"]
        out_path = output_dir / f"{seg_id}.wav"

        cmd = [
            FFMPEG,
            "-y",
            "-i",
            str(source_path),
            "-ss",
            str(start),
        ]
        if i + 1 < len(segments):
            cmd += ["-to", str(segments[i + 1]["start"])]
        cmd += ["-c:a", "pcm_s16le", str(out_path)]

        subprocess.run(cmd, check=True, capture_output=True)

        result[seg_id] = out_path

    return result
