from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AvatarResponse(BaseModel):
    id: str
    status: Literal["queued", "preparing", "ready", "failed"]
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class JobResponse(BaseModel):
    id: str
    avatar_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: float
    duration_seconds: float | None = None
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    video_url: str | None = None
    provenance_url: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    worker_running: bool
    ffmpeg_configured: bool
    musetalk_configured: bool
    liveportrait_enabled: bool
    gpu_index: int
    gpu_memory_limit_mb: int
    gpu_memory_fraction: float
