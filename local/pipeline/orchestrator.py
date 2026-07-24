from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from pipeline.audio_prep import prepare_audio
from pipeline.base_motion import fit_motion, make_static_base
from pipeline.config import Settings
from pipeline.lipsync import run_musetalk
from pipeline.postprocess import mux_audio


@dataclass(frozen=True, slots=True)
class RenderArtifacts:
    output_path: Path
    provenance_path: Path
    duration_seconds: float


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def render_video(
    *,
    job_id: str,
    avatar_id: str,
    reference_image: Path,
    input_audio: Path,
    work_dir: Path,
    output_dir: Path,
    settings: Settings,
    base_motion: Path | None = None,
    bbox_shift: int | None = None,
    progress: Callable[[float], None] | None = None,
) -> RenderArtifacts:
    """S0 -> S2 -> S3. S1 is represented by an optional cached LivePortrait base clip."""
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = progress or (lambda _: None)

    report(0.10)
    prepared_audio = prepare_audio(input_audio, work_dir, settings)
    report(0.25)

    if base_motion and base_motion.is_file():
        base_video = fit_motion(base_motion, prepared_audio.duration_seconds, work_dir, settings)
    else:
        base_video = make_static_base(
            reference_image, prepared_audio.duration_seconds, work_dir / "base_static.mp4", settings
        )
    report(0.40)

    raw_video = run_musetalk(
        base_video,
        prepared_audio.whisper_path,
        work_dir,
        settings,
        settings.musetalk_bbox_shift if bbox_shift is None else bbox_shift,
    )
    report(0.85)

    output_path = output_dir / f"{job_id}.mp4"
    mux_audio(raw_video, prepared_audio.master_path, output_path, settings)
    report(0.96)

    provenance_path = output_dir / f"{job_id}.provenance.json"
    provenance_path.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "avatar_id": avatar_id,
                "generated_at": datetime.now(UTC).isoformat(),
                "ai_generated": True,
                "pipeline": {
                    "lip_sync": "MuseTalk 1.5",
                    "motion": "LivePortrait" if base_motion else "static reference image",
                    "fps": 25,
                    "bbox_shift": settings.musetalk_bbox_shift if bbox_shift is None else bbox_shift,
                },
                "source_hashes": {
                    "reference_image_sha256": _sha256(reference_image),
                    "audio_sha256": _sha256(input_audio),
                },
                "duration_seconds": prepared_audio.duration_seconds,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report(1.0)
    return RenderArtifacts(output_path, provenance_path, prepared_audio.duration_seconds)

