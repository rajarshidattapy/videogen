from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


FPS = 25
WHISPER_SR = 16_000
MASTER_SR = 24_000


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _path(value: str | None, root: Path, fallback: str) -> Path:
    candidate = Path(value or fallback)
    return candidate if candidate.is_absolute() else (root / candidate).resolve()


def _venv_python(root: Path) -> str:
    candidates = (
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    # Keep the expected path in diagnostics even before the models are installed.
    return str(candidates[0])


def _executable(value: str | None, root: Path, fallback: str) -> str:
    """Resolve configured relative executable paths once, before a subprocess changes cwd."""
    if not value:
        return fallback
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate)
    # Bare commands such as `ffmpeg` are intentionally left for PATH lookup.
    if "/" not in value and "\\" not in value:
        return value
    return str((root / candidate).resolve())


def _load_project_dotenv() -> None:
    """Make the documented `.env` work without ever overriding deployment variables."""
    source_root = Path(__file__).resolve().parents[1]
    configured_root = Path(os.getenv("VIDEO_GEN_ROOT", source_root))
    if not configured_root.is_absolute():
        configured_root = (source_root / configured_root).resolve()
    load_dotenv(configured_root / ".env", override=False)


_load_project_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    root: Path
    data_dir: Path
    work_dir: Path
    out_dir: Path
    ffmpeg_bin: str
    ffprobe_bin: str
    musetalk_root: Path
    musetalk_python: str
    liveportrait_root: Path
    liveportrait_python: str
    idle_driver_path: Path
    enable_liveportrait: bool
    avatar_motion_seconds: int
    musetalk_bbox_shift: int
    musetalk_batch_size: int
    musetalk_use_float16: bool
    gpu_index: int
    gpu_memory_limit_mb: int
    gpu_memory_fraction: float
    face_validation: str
    max_upload_bytes: int
    max_audio_seconds: int
    keep_workdirs: bool
    cors_origins: tuple[str, ...]

    @property
    def avatar_dir(self) -> Path:
        return self.data_dir / "avatars"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "talkinghead.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        source_root = Path(__file__).resolve().parents[1]
        root = _path(os.getenv("VIDEO_GEN_ROOT"), source_root, ".")
        musetalk_root = _path(os.getenv("MUSE_TALK_ROOT"), root, "vendor/MuseTalk")
        liveportrait_root = _path(
            os.getenv("LIVEPORTRAIT_ROOT"), root, "vendor/LivePortrait"
        )
        raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        gpu_memory_limit_mb = int(os.getenv("GPU_MEMORY_LIMIT_MB", "3500"))
        gpu_memory_fraction = float(os.getenv("GPU_MEMORY_FRACTION", "0.90"))
        if gpu_memory_limit_mb < 512:
            raise ValueError("GPU_MEMORY_LIMIT_MB must be at least 512.")
        if not 0 < gpu_memory_fraction <= 1:
            raise ValueError("GPU_MEMORY_FRACTION must be greater than 0 and at most 1.")
        return cls(
            root=root,
            data_dir=_path(os.getenv("DATA_DIR"), root, "data"),
            work_dir=_path(os.getenv("WORK_DIR"), root, "work"),
            out_dir=_path(os.getenv("OUT_DIR"), root, "out"),
            ffmpeg_bin=_executable(os.getenv("FFMPEG_BIN"), root, "ffmpeg"),
            ffprobe_bin=_executable(os.getenv("FFPROBE_BIN"), root, "ffprobe"),
            musetalk_root=musetalk_root,
            musetalk_python=_executable(
                os.getenv("MUSE_TALK_PYTHON"), root, _venv_python(musetalk_root)
            ),
            liveportrait_root=liveportrait_root,
            liveportrait_python=_executable(
                os.getenv("LIVEPORTRAIT_PYTHON"), root, _venv_python(liveportrait_root)
            ),
            idle_driver_path=_path(
                os.getenv("IDLE_DRIVER_PATH"), root, "assets/drivers/neutral_subtle.mp4"
            ),
            enable_liveportrait=_truthy(os.getenv("ENABLE_LIVEPORTRAIT")),
            avatar_motion_seconds=int(os.getenv("AVATAR_MOTION_SECONDS", "30")),
            musetalk_bbox_shift=int(os.getenv("MUSE_TALK_BBOX_SHIFT", "0")),
            musetalk_batch_size=int(os.getenv("MUSE_TALK_BATCH_SIZE", "1")),
            musetalk_use_float16=_truthy(os.getenv("MUSE_TALK_USE_FLOAT16"), True),
            gpu_index=int(os.getenv("GPU_INDEX", "0")),
            gpu_memory_limit_mb=gpu_memory_limit_mb,
            gpu_memory_fraction=gpu_memory_fraction,
            face_validation=os.getenv("FACE_VALIDATION", "basic").strip().lower(),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024,
            max_audio_seconds=int(os.getenv("MAX_AUDIO_SECONDS", "120")),
            keep_workdirs=_truthy(os.getenv("KEEP_WORKDIRS")),
            cors_origins=tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip()),
        )

    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.avatar_dir, self.work_dir, self.out_dir):
            directory.mkdir(parents=True, exist_ok=True)
