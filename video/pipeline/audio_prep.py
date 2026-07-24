from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from pipeline.commands import require_executable, run_command
from pipeline.config import MASTER_SR, WHISPER_SR, FPS, Settings
from pipeline.errors import PipelineError


@dataclass(frozen=True, slots=True)
class PreparedAudio:
    whisper_path: Path
    master_path: Path
    duration_seconds: float
    frame_count: int


def audio_duration(path: Path, settings: Settings) -> float:
    require_executable(settings.ffprobe_bin, "ffprobe")
    result = run_command(
        [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            path,
        ],
        label="ffprobe",
    )
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PipelineError("Could not read a duration from the uploaded audio file.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise PipelineError("The uploaded audio file has no playable audio stream.")
    return duration


def prepare_audio(source: Path, work_dir: Path, settings: Settings) -> PreparedAudio:
    require_executable(settings.ffmpeg_bin, "ffmpeg")
    source_duration = audio_duration(source, settings)
    if source_duration > settings.max_audio_seconds:
        raise PipelineError(
            f"Audio is {source_duration:.1f}s long; the service limit is "
            f"{settings.max_audio_seconds}s. Split it into smaller clips and retry."
        )

    whisper_path = work_dir / "audio_16k.wav"
    master_path = work_dir / "audio_master.wav"
    audio_filter = "apad=pad_dur=0.2,adelay=200|200"
    for destination, sample_rate in ((whisper_path, WHISPER_SR), (master_path, MASTER_SR)):
        run_command(
            [
                settings.ffmpeg_bin,
                "-y",
                "-i",
                source,
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-af",
                audio_filter,
                destination,
            ],
            label="ffmpeg audio preparation",
        )
    duration = audio_duration(master_path, settings)
    return PreparedAudio(
        whisper_path=whisper_path,
        master_path=master_path,
        duration_seconds=duration,
        frame_count=math.ceil(duration * FPS),
    )

