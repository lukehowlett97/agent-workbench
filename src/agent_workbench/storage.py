"""Safe file validation and per-job workspace storage."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

ALLOWED_SUFFIXES = {".csv", ".json", ".md", ".pdf", ".txt"}
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class StoredFile:
    """Metadata for one stored upload."""

    original_name: str
    stored_name: str
    size: int
    sha256: str


async def store_uploads(
    uploads: list[UploadFile],
    workspace: Path,
    max_file_bytes: int,
    max_job_bytes: int,
) -> list[StoredFile]:
    """Validate and store uploads without trusting client filenames."""
    input_dir = workspace / "input"
    (workspace / "work").mkdir(parents=True, exist_ok=False)
    (workspace / "output").mkdir(parents=True, exist_ok=False)
    input_dir.mkdir(parents=True, exist_ok=False)

    stored: list[StoredFile] = []
    job_size = 0

    for index, upload in enumerate(uploads, start=1):
        original = Path(upload.filename or "unnamed").name
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValueError(f"Unsupported file type: {suffix or 'none'}")

        safe_stem = SAFE_NAME.sub("-", Path(original).stem).strip("-._") or "file"
        stored_name = f"{index:03d}-{safe_stem[:80]}{suffix}"
        destination = input_dir / stored_name
        digest = hashlib.sha256()
        size = 0

        with destination.open("xb") as stream:
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                job_size += len(chunk)
                if size > max_file_bytes or job_size > max_job_bytes:
                    stream.close()
                    destination.unlink(missing_ok=True)
                    raise ValueError("Upload size limit exceeded.")
                digest.update(chunk)
                stream.write(chunk)

        stored.append(
            StoredFile(original, stored_name, size, digest.hexdigest())
        )

    return stored
