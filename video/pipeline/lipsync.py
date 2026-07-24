from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from pipeline.commands import run_command
from pipeline.config import Settings
from pipeline.errors import PipelineError, ToolUnavailable


def _assert_musetalk_ready(settings: Settings) -> tuple[Path, Path]:
    if not settings.musetalk_root.is_dir() or not Path(settings.musetalk_python).is_file():
        raise ToolUnavailable(
            "MuseTalk is not installed. Set MUSE_TALK_ROOT and MUSE_TALK_PYTHON to the "
            "MuseTalk checkout and its Python 3.11 environment."
        )
    unet = settings.musetalk_root / "models" / "musetalkV15" / "unet.pth"
    model_config = settings.musetalk_root / "models" / "musetalkV15" / "musetalk.json"
    missing = [path.name for path in (unet, model_config) if not path.is_file()]
    if missing:
        raise ToolUnavailable(
            "MuseTalk weights are incomplete (missing "
            + ", ".join(missing)
            + "). Run the vendor checkout's weight download script first."
        )
    return unet, model_config


def _ffmpeg_directory(settings: Settings) -> Path:
    configured = Path(settings.ffmpeg_bin)
    if configured.is_file():
        return configured.parent
    located = shutil.which(settings.ffmpeg_bin)
    if located:
        return Path(located).parent
    raise ToolUnavailable("FFmpeg is not available. Set FFMPEG_BIN to the ffmpeg executable path.")


def run_musetalk(
    base_video: Path,
    whisper_audio: Path,
    work_dir: Path,
    settings: Settings,
    bbox_shift: int | None = None,
) -> Path:
    """Run batch MuseTalk; the model boundary stays isolated for a future LatentSync swap."""
    unet, model_config = _assert_musetalk_ready(settings)
    ffmpeg_directory = _ffmpeg_directory(settings)
    result_dir = work_dir / "musetalk_result"
    result_dir.mkdir(parents=True, exist_ok=True)
    inference_config = work_dir / "musetalk.yaml"
    inference_config.write_text(
        yaml.safe_dump(
            {
                "task_0": {
                    "video_path": str(base_video.resolve()),
                    "audio_path": str(whisper_audio.resolve()),
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    command: list[str | Path] = [
        settings.musetalk_python,
        settings.root / "pipeline" / "musetalk_gpu_runner.py",
        "--gpu-index",
        str(settings.gpu_index),
        "--gpu-memory-limit-mb",
        str(settings.gpu_memory_limit_mb),
        "--gpu-memory-fraction",
        str(settings.gpu_memory_fraction),
        "--",
        "-m",
        "scripts.inference",
        "--inference_config",
        inference_config,
        "--result_dir",
        result_dir,
        "--unet_model_path",
        unet,
        "--unet_config",
        model_config,
        "--version",
        "v15",
        "--ffmpeg_path",
        ffmpeg_directory,
        "--batch_size",
        str(settings.musetalk_batch_size),
    ]
    if settings.musetalk_use_float16:
        command.append("--use_float16")
    if bbox_shift is not None:
        command.extend(["--bbox_shift", str(bbox_shift)])
    run_command(command, cwd=settings.musetalk_root, label="MuseTalk lip-sync")
    candidates = sorted(result_dir.rglob("*.mp4"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise PipelineError("MuseTalk completed but did not produce a lip-synced MP4.")
    return candidates[-1]
