"""Storage interfaces.

`BlobStore` is the audio-blob abstraction; keeping the pipeline coded
against this Protocol (not a concrete class) is what allows a later move
to object storage without touching callers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class BlobStore(Protocol):
    """Content store for audio blobs, keyed by relative POSIX-style paths."""

    def put(self, key: str, data: bytes) -> None:
        """Store `data` under `key`, overwriting any existing blob."""
        ...

    def get(self, key: str) -> bytes:
        """Return the blob's bytes. Raises KeyError if absent."""
        ...

    def exists(self, key: str) -> bool:
        """True iff a blob is stored under `key`."""
        ...

    def delete(self, key: str) -> None:
        """Remove the blob. Raises KeyError if absent."""
        ...

    def path(self, key: str) -> Path:
        """Local filesystem path for the blob (for FileResponse serving).

        Non-local backends may raise NotImplementedError.
        """
        ...
