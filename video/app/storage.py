from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from pipeline.errors import PipelineError


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def safe_suffix(filename: str | None, allowed: set[str], kind: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in allowed:
        options = ", ".join(sorted(allowed))
        raise PipelineError(f"Unsupported {kind} file type. Use one of: {options}.")
    return suffix


async def save_upload(upload: UploadFile, destination: Path, max_bytes: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise PipelineError(f"Upload exceeds the {max_bytes // (1024 * 1024)}MB limit.")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    if written == 0:
        destination.unlink(missing_ok=True)
        raise PipelineError("The uploaded file is empty.")

