from __future__ import annotations

import logging
import shutil
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.database import Database
from app.schemas import AvatarResponse, HealthResponse, JobResponse
from app.storage import AUDIO_SUFFIXES, IMAGE_SUFFIXES, safe_suffix, save_upload
from app.validation import validate_reference_image
from app.worker import SingleGpuWorker
from pipeline.config import Settings
from pipeline.errors import PipelineError


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = Settings.from_env()
database = Database(settings.database_path)


def _avatar_response(row: object) -> AvatarResponse:
    return AvatarResponse(
        id=row["id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error=row["error_message"],
    )


def _job_response(row: object) -> JobResponse:
    completed = row["status"] == "completed"
    return JobResponse(
        id=row["id"],
        avatar_id=row["avatar_id"],
        status=row["status"],
        progress=row["progress"],
        duration_seconds=row["duration_seconds"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error=row["error_message"],
        video_url=f"/jobs/{row['id']}/video" if completed else None,
        provenance_url=f"/jobs/{row['id']}/provenance" if completed else None,
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.ensure_directories()
    database.initialise()
    database.recover_inflight_work()
    worker = SingleGpuWorker(database, settings)
    worker.start()
    app.state.worker = worker
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(
    title="Talking Head Video API",
    version="0.1.0",
    description="Send a consented portrait and the MP3 returned by Sarvam to receive a lip-synced MP4.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    worker = getattr(app.state, "worker", None)
    return HealthResponse(
        status="ok" if worker and worker.running else "degraded",
        worker_running=bool(worker and worker.running),
        ffmpeg_configured=shutil.which(settings.ffmpeg_bin) is not None
        or Path(settings.ffmpeg_bin).is_file(),
        musetalk_configured=settings.musetalk_root.is_dir()
        and Path(settings.musetalk_python).is_file(),
        liveportrait_enabled=settings.enable_liveportrait,
        gpu_index=settings.gpu_index,
        gpu_memory_limit_mb=settings.gpu_memory_limit_mb,
        gpu_memory_fraction=settings.gpu_memory_fraction,
    )


@app.post("/avatars", response_model=AvatarResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_avatar(
    image: Annotated[UploadFile, File(description="A sharp, front-facing reference portrait")],
    consent_confirmed: Annotated[
        bool, Form(description="Must confirm that the depicted person gave recorded consent")
    ],
    consent_subject: Annotated[str | None, Form()] = None,
) -> AvatarResponse:
    if not consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recorded consent from the depicted person is required before creating an avatar.",
        )
    try:
        suffix = safe_suffix(image.filename, IMAGE_SUFFIXES, "image")
        avatar_id = uuid.uuid4().hex
        image_path = settings.avatar_dir / avatar_id / f"reference{suffix}"
        await save_upload(image, image_path, settings.max_upload_bytes)
        validate_reference_image(image_path, settings.face_validation)
        row = database.create_avatar(avatar_id, image_path, consent_subject)
        return _avatar_response(row)
    except PipelineError as exc:
        if "image_path" in locals():
            image_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@app.get("/avatars/{avatar_id}", response_model=AvatarResponse)
def get_avatar(avatar_id: str) -> AvatarResponse:
    row = database.get_avatar(avatar_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Avatar not found.")
    return _avatar_response(row)


@app.post("/render", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
@app.post("/renders", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_render(
    avatar_id: Annotated[str, Form()],
    audio: Annotated[UploadFile, File(description="MP3 or other audio returned by Sarvam")],
    bbox_shift: Annotated[int | None, Form()] = None,
) -> JobResponse:
    avatar = database.get_avatar(avatar_id)
    if avatar is None:
        raise HTTPException(status_code=404, detail="Avatar not found.")
    if avatar["status"] != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Avatar is {avatar['status']}. Wait for it to become ready before rendering.",
        )
    if bbox_shift is not None and not -20 <= bbox_shift <= 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox_shift must be between -20 and 20. Tune within MuseTalk's reported face range.",
        )
    try:
        suffix = safe_suffix(audio.filename, AUDIO_SUFFIXES, "audio")
        job_id = uuid.uuid4().hex
        audio_path = settings.work_dir / job_id / f"input{suffix}"
        await save_upload(audio, audio_path, settings.max_upload_bytes)
        row = database.create_job(job_id, avatar_id, audio_path, bbox_shift)
        return _job_response(row)
    except PipelineError as exc:
        if "audio_path" in locals():
            audio_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    row = database.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Render job not found.")
    return _job_response(row)


@app.get("/jobs/{job_id}/video")
def get_video(job_id: str) -> FileResponse:
    row = database.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Render job not found.")
    if row["status"] != "completed" or not row["output_path"]:
        raise HTTPException(status_code=409, detail="Video is not ready yet.")
    output_path = Path(row["output_path"])
    if not output_path.is_file():
        raise HTTPException(status_code=410, detail="The completed video file is no longer available.")
    return FileResponse(output_path, media_type="video/mp4", filename=f"talking-head-{job_id}.mp4")


@app.get("/jobs/{job_id}/provenance")
def get_provenance(job_id: str) -> FileResponse:
    row = database.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Render job not found.")
    if row["status"] != "completed" or not row["provenance_path"]:
        raise HTTPException(status_code=409, detail="Provenance record is not ready yet.")
    provenance_path = Path(row["provenance_path"])
    if not provenance_path.is_file():
        raise HTTPException(status_code=410, detail="The provenance record is no longer available.")
    return FileResponse(provenance_path, media_type="application/json")
