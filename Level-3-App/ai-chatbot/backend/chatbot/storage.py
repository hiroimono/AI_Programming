"""Document storage backend abstraction.

Uploaded training files (PDF, DOCX, XLSX, TXT) are kept as raw bytes on
disk (or cloud later) for two reasons:
  1. Re-processing: if we change chunker / embedder later, we can re-run
     against the original file without asking the tenant to re-upload.
  2. Source attribution: the admin panel can offer a "download original".

The Protocol seam lets us swap LocalStorageBackend for R2 / Hetzner
Object Storage in production without touching parsers, pipeline, or
endpoints — they all go through `get_storage()`.

Blob layout is keyed by (tenant_id, bot_id) so a tenant's files never
share a directory with another tenant's — defense in depth on top of RLS
(which only guards the DB, not the filesystem).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

from chatbot.config import get_settings


class StorageBackend(Protocol):
    """Minimal interface every storage backend must implement.

    `storage_path` is an opaque string the backend understands; callers
    treat it as a blob handle and never parse it.
    """

    def save(self, content: bytes, tenant_id: str, bot_id: str, filename: str) -> str:
        """Persist `content`, return an opaque storage_path."""

    def read(self, storage_path: str) -> bytes:
        """Read previously-saved bytes."""

    def delete(self, storage_path: str) -> None:
        """Remove the blob. Idempotent: missing blobs do not error."""


class LocalStorageBackend:
    """Filesystem backend used for development / single-host deployments.

    Layout on disk:
        {root}/{tenant_id}/{bot_id}/{uuid}-{safe_filename}

    The UUID prefix prevents collisions when two uploads share a name.
    `safe_filename` strips path separators so a malicious filename cannot
    escape the bot's directory.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize(filename: str) -> str:
        # Drop directory components and null bytes; keep extension intact.
        clean = filename.replace("\x00", "").replace("/", "_").replace("\\", "_")
        clean = clean.lstrip(".")  # block ".env"-style hidden names
        return clean or "unnamed"

    def save(self, content: bytes, tenant_id: str, bot_id: str, filename: str) -> str:
        safe = self._sanitize(filename)
        target_dir = self._root / tenant_id / bot_id
        target_dir.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}-{safe}"
        target = target_dir / unique_name
        target.write_bytes(content)
        # Return path relative to root so storage_path stays portable if
        # we ever migrate the root directory.
        return str(target.relative_to(self._root).as_posix())

    def read(self, storage_path: str) -> bytes:
        target = self._resolve(storage_path)
        return target.read_bytes()

    def delete(self, storage_path: str) -> None:
        target = self._resolve(storage_path)
        target.unlink(missing_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        # Resolve and confirm the path is still inside _root — defense
        # against a tampered storage_path coming back from the DB.
        candidate = (self._root / storage_path).resolve()
        if self._root not in candidate.parents and candidate != self._root:
            raise ValueError(f"storage_path escapes root: {storage_path!r}")
        return candidate


_SINGLETON: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the configured storage backend (cached singleton)."""
    global _SINGLETON  # pylint: disable=global-statement
    if _SINGLETON is None:
        settings = get_settings()
        if settings.storage_backend == "local":
            _SINGLETON = LocalStorageBackend(settings.storage_local_path)
        else:
            raise NotImplementedError(
                f"storage_backend={settings.storage_backend!r} not supported yet"
            )
    return _SINGLETON
