"""Document storage backend abstraction.

The rag-service receives uploaded files (PDF, DOCX, XLSX, TXT) from the
consuming app backends. We keep the raw bytes on disk (or cloud later)
for two reasons:
  1. Re-processing: if we change chunker / embedder later, we can re-run
     against the original file without asking the user to re-upload.
  2. Source attribution: the UI can offer a "download original" link.

Backend abstraction lets us swap LocalStorage for R2 / Hetzner Object
Storage in production without touching parsers or endpoints — they all
go through `get_storage()`.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

from rag_service.config import get_settings


class StorageBackend(Protocol):
    """Minimal interface every storage backend must implement.

    `storage_path` is an opaque string the backend understands; callers
    treat it as a blob handle and never parse it.
    """

    def save(self, content: bytes, app_id: str, user_id: str, filename: str) -> str:
        """Persist `content`, return an opaque storage_path."""

    def read(self, storage_path: str) -> bytes:
        """Read previously-saved bytes."""

    def delete(self, storage_path: str) -> None:
        """Remove the blob. Idempotent: missing blobs do not error."""


class LocalStorageBackend:
    """Filesystem backend used for development / single-host deployments.

    Layout on disk:
        {root}/{app_id}/{user_id}/{uuid}-{safe_filename}

    The UUID prefix prevents collisions when the same user uploads two
    files with identical names. `safe_filename` strips path separators
    so a malicious filename cannot escape the user's directory.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize(filename: str) -> str:
        # Drop directory components and null bytes; keep extension intact.
        # We do not sanitize unicode — the FS handles it; we only block
        # traversal characters.
        clean = filename.replace("\x00", "").replace("/", "_").replace("\\", "_")
        clean = clean.lstrip(".")  # block ".env" style names becoming hidden
        return clean or "unnamed"

    def save(self, content: bytes, app_id: str, user_id: str, filename: str) -> str:
        safe = self._sanitize(filename)
        target_dir = self._root / app_id / user_id
        target_dir.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}-{safe}"
        target = target_dir / unique_name
        target.write_bytes(content)
        # Return path relative to root so storage_path is portable if we
        # ever migrate the root directory.
        return str(target.relative_to(self._root).as_posix())

    def read(self, storage_path: str) -> bytes:
        target = self._resolve(storage_path)
        return target.read_bytes()

    def delete(self, storage_path: str) -> None:
        target = self._resolve(storage_path)
        target.unlink(missing_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        # Resolve and confirm the path is still inside _root — defense
        # against a tampered storage_path coming back from DB.
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
