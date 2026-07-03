"""Filesystem-backed BlobStore for the MVP."""

from __future__ import annotations

from pathlib import Path


class LocalBlobStore:
    """Stores blobs as files under ``root``.

    Keys are relative POSIX-style paths (e.g. ``roots/a1.wav``). Keys that
    would resolve outside ``root`` are rejected to prevent path traversal.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        root = self.root.resolve()
        target = (root / key).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"key escapes storage root: {key!r}")
        return target

    def put(self, key: str, data: bytes) -> None:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def get(self, key: str) -> bytes:
        target = self._resolve(key)
        if not target.is_file():
            raise KeyError(key)
        return target.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        if not target.is_file():
            raise KeyError(key)
        target.unlink()

    def path(self, key: str) -> Path:
        return self._resolve(key)
