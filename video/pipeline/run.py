from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from pathlib import Path

from pipeline.config import Settings
from pipeline.orchestrator import render_video


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an MP3/WAV into a lip-synced talking-head MP4.")
    parser.add_argument("--image", required=True, type=Path, help="Front-facing reference portrait")
    parser.add_argument("--audio", required=True, type=Path, help="Audio received from Sarvam")
    parser.add_argument("--output", type=Path, help="Destination MP4 (default: out/<job-id>.mp4)")
    parser.add_argument("--base-motion", type=Path, help="Optional cached LivePortrait base-motion MP4")
    parser.add_argument("--bbox-shift", type=int, help="MuseTalk mouth-mask setting for this render")
    args = parser.parse_args()

    settings = Settings.from_env()
    settings.ensure_directories()
    if not args.image.is_file() or not args.audio.is_file():
        parser.error("--image and --audio must point to existing files")
    job_id = uuid.uuid4().hex
    work_dir = settings.work_dir / job_id
    output_dir = args.output.parent.resolve() if args.output else settings.out_dir
    try:
        result = render_video(
            job_id=job_id,
            avatar_id="cli",
            reference_image=args.image.resolve(),
            input_audio=args.audio.resolve(),
            work_dir=work_dir,
            output_dir=output_dir,
            settings=settings,
            base_motion=args.base_motion.resolve() if args.base_motion else None,
            bbox_shift=args.bbox_shift,
            progress=lambda value: print(f"progress={value:.0%}", flush=True),
        )
        if args.output:
            shutil.copy2(result.output_path, args.output)
            print(args.output.resolve())
        else:
            print(result.output_path)
        return 0
    finally:
        if not settings.keep_workdirs:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

