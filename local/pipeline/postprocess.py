from __future__ import annotations

from pathlib import Path

from pipeline.commands import require_executable, run_command
from pipeline.config import Settings


def mux_audio(raw_video: Path, master_audio: Path, output_path: Path, settings: Settings) -> Path:
    """Encode a broadly playable H.264/AAC MP4 and retain Sarvam's 24kHz master audio."""
    require_executable(settings.ffmpeg_bin, "ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            raw_video,
            "-i",
            master_audio,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            output_path,
        ],
        label="ffmpeg final encode",
    )
    return output_path

