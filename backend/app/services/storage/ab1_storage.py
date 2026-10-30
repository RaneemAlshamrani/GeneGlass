
"""Secure storage utilities for uploaded AB1 sequencing files."""

import hashlib
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

BACKEND_DIR = Path(__file__).resolve().parents[3]
UPLOAD_ROOT = BACKEND_DIR / "uploads"

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB


async def save_ab1_file(
    upload: UploadFile,
    user_id: int,
) -> tuple[Path, str]:
    """Validate and store an AB1 file in the owner's directory."""

    original_name = Path(upload.filename or "").name

    if not original_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file name is required.",
        )

    if not re.search(r"\.ab1$", original_name, re.IGNORECASE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .ab1 files are accepted.",
        )

    if user_id < 1:
        raise ValueError("Invalid user ID.")

    user_upload_dir = UPLOAD_ROOT / f"user_{user_id}"
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    destination = user_upload_dir / f"{uuid.uuid4().hex}.ab1"

    sha256 = hashlib.sha256()
    total_size = 0

    try:
        with destination.open("xb") as output:
            while True:
                chunk = await upload.read(CHUNK_SIZE)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File size must not exceed 20 MB.",
                    )

                sha256.update(chunk)
                output.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        with destination.open("rb") as saved_file:
            signature = saved_file.read(4)

        if signature != b"ABIF":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The file content is not a valid ABIF file.",
            )

        return destination, sha256.hexdigest()

    except Exception:
        destination.unlink(missing_ok=True)
        raise

    finally:
        await upload.close()
