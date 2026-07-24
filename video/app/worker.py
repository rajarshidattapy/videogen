from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path

from app.database import Database
from pipeline.base_motion import prepare_avatar_motion
from pipeline.config import Settings
from pipeline.errors import PipelineError
from pipeline.orchestrator import render_video


logger = logging.getLogger(__name__)


class SingleGpuWorker:
    """A deliberately serial worker: two MuseTalk jobs on one GPU are slower than one."""

    def __init__(self, database: Database, settings: Settings, poll_seconds: float = 0.5) -> None:
        self.database = database
        self.settings = settings
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="talkinghead-gpu-worker", daemon=True)

    @property
    def running(self) -> bool:
        return self._thread.is_alive() and not self._stop.is_set()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        # A running GPU subprocess cannot be safely abandoned while it owns the job's files and
        # SQLite connection. Finish the current item, then exit cleanly on the next loop.
        self._thread.join()

    def _run(self) -> None:
        while not self._stop.is_set():
            # Readied avatars unlock render submissions. A render always has a ready avatar.
            avatar = self.database.claim_next_avatar()
            if avatar is not None:
                self._prepare_avatar(avatar)
                continue
            job = self.database.claim_next_job()
            if job is not None:
                self._render(job)
                continue
            self._stop.wait(self.poll_seconds)

    @staticmethod
    def _safe_error(error: Exception) -> str:
        message = str(error).strip() or "Unexpected pipeline failure. Check server logs and retry."
        return message[-4_000:]

    def _prepare_avatar(self, avatar: object) -> None:
        avatar_id = avatar["id"]  # sqlite Row
        try:
            avatar_dir = self.settings.avatar_dir / avatar_id
            motion = prepare_avatar_motion(Path(avatar["image_path"]), avatar_dir, self.settings)
            self.database.mark_avatar_ready(avatar_id, motion)
            logger.info("Avatar %s is ready", avatar_id)
        except (PipelineError, OSError) as exc:
            logger.exception("Avatar preparation failed for %s", avatar_id)
            self.database.mark_avatar_failed(avatar_id, self._safe_error(exc))

    def _render(self, job: object) -> None:
        job_id = job["id"]
        work_dir = self.settings.work_dir / job_id
        try:
            avatar = self.database.get_avatar(job["avatar_id"])
            if avatar is None or avatar["status"] != "ready":
                raise PipelineError("Avatar is not ready. Wait for avatar preparation, then retry the render.")
            artifacts = render_video(
                job_id=job_id,
                avatar_id=job["avatar_id"],
                reference_image=Path(avatar["image_path"]),
                input_audio=Path(job["audio_path"]),
                work_dir=work_dir,
                output_dir=self.settings.out_dir,
                settings=self.settings,
                base_motion=Path(avatar["base_motion_path"])
                if avatar["base_motion_path"]
                else None,
                bbox_shift=job["bbox_shift"],
                progress=lambda value: self.database.update_job_progress(job_id, value),
            )
            self.database.mark_job_completed(
                job_id, artifacts.output_path, artifacts.provenance_path, artifacts.duration_seconds
            )
            logger.info("Render %s completed", job_id)
        except (PipelineError, OSError) as exc:
            logger.exception("Render failed for %s", job_id)
            self.database.mark_job_failed(job_id, self._safe_error(exc))
        finally:
            if not self.settings.keep_workdirs:
                shutil.rmtree(work_dir, ignore_errors=True)
