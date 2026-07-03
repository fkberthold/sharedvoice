"""Storage layer: a swappable blob store (audio) + a SQLite metadata helper.

The BlobStore abstraction is what lets audio move from the local
filesystem to object storage later without touching the pipeline.
"""
