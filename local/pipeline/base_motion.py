from __future__ import annotations

from pathlib import Path

from pipeline.commands import require_executable, run_command
from pipeline.config import FPS, Settings
from pipeline.errors import PipelineError, ToolUnavailable


def _normalise_video(source: Path, destination: Path, settings: Settings) -> Path:
    run_command(
        [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            source,
            "-an",
            "-r",
            str(FPS),
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            destination,
        ],
        label="ffmpeg video normalisation",
    )
    return destination


def make_static_base(image_path: Path, duration_seconds: float, destination: Path, settings: Settings) -> Path:
    """Turn a reference image into a CFR base clip for MuseTalk's batch runner."""
    require_executable(settings.ffmpeg_bin, "ffmpeg")
    run_command(
        [
            settings.ffmpeg_bin,
            "-y",
            "-loop",
            "1",
            "-i",
            image_path,
            "-t",
            f"{duration_seconds:.3f}",
            "-an",
            "-r",
            str(FPS),
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            destination,
        ],
        label="ffmpeg static base video",
    )
    return destination


def fit_motion(base_motion: Path, duration_seconds: float, work_dir: Path, settings: Settings) -> Path:
    """Ping-pong then loop a motion clip so it stays CFR 25fps without a hard seam."""
    require_executable(settings.ffmpeg_bin, "ffmpeg")
    ping_pong = work_dir / "motion_ping_pong.mp4"
    fitted = work_dir / "base_motion.mp4"
    run_command(
        [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            base_motion,
            "-filter_complex",
            "[0:v]reverse[r];[0:v][r]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-an",
            "-r",
            str(FPS),
            "-pix_fmt",
            "yuv420p",
            ping_pong,
        ],
        label="ffmpeg motion ping-pong",
    )
    run_command(
        [
            settings.ffmpeg_bin,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            ping_pong,
            "-t",
            f"{duration_seconds:.3f}",
            "-an",
            "-r",
            str(FPS),
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            fitted,
        ],
        label="ffmpeg motion fitting",
    )
    return fitted


def prepare_avatar_motion(image_path: Path, avatar_dir: Path, settings: Settings) -> Path | None:
    """Create and cache a 30 second LivePortrait base clip for an avatar."""
    if not settings.enable_liveportrait:
        return None
    if not settings.idle_driver_path.is_file():
        raise ToolUnavailable(
            "LivePortrait is enabled but IDLE_DRIVER_PATH is missing. Add a closed-mouth "
            "driver video and set IDLE_DRIVER_PATH."
        )
    if not settings.liveportrait_root.is_dir() or not Path(settings.liveportrait_python).is_file():
        raise ToolUnavailable(
            "LivePortrait is not installed. Set LIVEPORTRAIT_ROOT and LIVEPORTRAIT_PYTHON "
            "to its checkout and Python 3.11 environment."
        )

    require_executable(settings.ffmpeg_bin, "ffmpeg")
    stage_dir = avatar_dir / "liveportrait"
    stage_dir.mkdir(parents=True, exist_ok=True)
    driver_fit = stage_dir / "driver_fit.mp4"
    # The fixed cache is subsequently ping-ponged again per audio render.
    fit_motion(settings.idle_driver_path, settings.avatar_motion_seconds, stage_dir, settings)
    generated_driver = stage_dir / "base_motion.mp4"
    generated_driver.replace(driver_fit)

    output_dir = stage_dir / "raw"
    output_dir.mkdir(exist_ok=True)
    run_command(
        [
            settings.liveportrait_python,
            settings.root / "pipeline" / "musetalk_gpu_runner.py",
            "--gpu-index",
            str(settings.gpu_index),
            "--gpu-memory-limit-mb",
            str(settings.gpu_memory_limit_mb),
            "--gpu-memory-fraction",
            str(settings.gpu_memory_fraction),
            "--",
            "--script",
            "inference.py",
            "-s",
            image_path,
            "-d",
            driver_fit,
            "-o",
            output_dir,
            "--flag_pasteback",
        ],
        cwd=settings.liveportrait_root,
        label="LivePortrait",
    )
    candidates = sorted(output_dir.rglob("*.mp4"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise PipelineError("LivePortrait completed but did not produce an MP4 base-motion video.")
    return _normalise_video(candidates[-1], avatar_dir / "base_motion.mp4", settings)
