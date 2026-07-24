from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    """Tiny durable queue. One worker claims work at a time using SQLite transactions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._schema_lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialise(self) -> None:
        with self._schema_lock:
            connection = self._connect()
            try:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS avatars (
                        id TEXT PRIMARY KEY,
                        status TEXT NOT NULL CHECK (status IN ('queued', 'preparing', 'ready', 'failed')),
                        image_path TEXT NOT NULL,
                        base_motion_path TEXT,
                        consent_subject TEXT,
                        consent_recorded_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        error_message TEXT
                    );

                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        avatar_id TEXT NOT NULL REFERENCES avatars(id),
                        status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
                        audio_path TEXT NOT NULL,
                        output_path TEXT,
                        provenance_path TEXT,
                        duration_seconds REAL,
                        progress REAL NOT NULL DEFAULT 0,
                        bbox_shift INTEGER,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        error_message TEXT
                    );
                    CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status, created_at);
                    CREATE INDEX IF NOT EXISTS avatars_status_created ON avatars(status, created_at);
                    """
                )
            finally:
                connection.close()

    def recover_inflight_work(self) -> None:
        now = utcnow()
        with self._transaction() as connection:
            connection.execute(
                "UPDATE avatars SET status = 'queued', updated_at = ? WHERE status = 'preparing'", (now,)
            )
            connection.execute(
                "UPDATE jobs SET status = 'queued', progress = 0, updated_at = ? WHERE status = 'processing'",
                (now,),
            )

    def create_avatar(
        self, avatar_id: str, image_path: Path, consent_subject: str | None
    ) -> sqlite3.Row:
        now = utcnow()
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO avatars (
                    id, status, image_path, consent_subject, consent_recorded_at, created_at, updated_at
                ) VALUES (?, 'queued', ?, ?, ?, ?, ?)""",
                (avatar_id, str(image_path), consent_subject, now, now, now),
            )
            return connection.execute("SELECT * FROM avatars WHERE id = ?", (avatar_id,)).fetchone()

    def get_avatar(self, avatar_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute("SELECT * FROM avatars WHERE id = ?", (avatar_id,)).fetchone()

    def claim_next_avatar(self) -> sqlite3.Row | None:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM avatars WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            now = utcnow()
            connection.execute(
                "UPDATE avatars SET status = 'preparing', updated_at = ?, error_message = NULL WHERE id = ?",
                (now, row["id"]),
            )
            return connection.execute("SELECT * FROM avatars WHERE id = ?", (row["id"],)).fetchone()

    def mark_avatar_ready(self, avatar_id: str, base_motion_path: Path | None) -> None:
        with self._transaction() as connection:
            connection.execute(
                """UPDATE avatars SET status = 'ready', base_motion_path = ?, error_message = NULL,
                   updated_at = ? WHERE id = ?""",
                (str(base_motion_path) if base_motion_path else None, utcnow(), avatar_id),
            )

    def mark_avatar_failed(self, avatar_id: str, message: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE avatars SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
                (message, utcnow(), avatar_id),
            )

    def create_job(
        self, job_id: str, avatar_id: str, audio_path: Path, bbox_shift: int | None
    ) -> sqlite3.Row:
        now = utcnow()
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO jobs (
                    id, avatar_id, status, audio_path, bbox_shift, created_at, updated_at
                ) VALUES (?, ?, 'queued', ?, ?, ?, ?)""",
                (job_id, avatar_id, str(audio_path), bbox_shift, now, now),
            )
            return connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    def get_job(self, job_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    def claim_next_job(self) -> sqlite3.Row | None:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            now = utcnow()
            connection.execute(
                """UPDATE jobs SET status = 'processing', progress = 0.03, error_message = NULL,
                   updated_at = ? WHERE id = ?""",
                (now, row["id"]),
            )
            return connection.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()

    def update_job_progress(self, job_id: str, progress: float) -> None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE jobs SET progress = ?, updated_at = ? WHERE id = ?",
                (max(0.0, min(1.0, progress)), utcnow(), job_id),
            )

    def mark_job_completed(
        self,
        job_id: str,
        output_path: Path,
        provenance_path: Path,
        duration_seconds: float,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """UPDATE jobs SET status = 'completed', output_path = ?, provenance_path = ?,
                   duration_seconds = ?, progress = 1, error_message = NULL, updated_at = ? WHERE id = ?""",
                (str(output_path), str(provenance_path), duration_seconds, utcnow(), job_id),
            )

    def mark_job_failed(self, job_id: str, message: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                """UPDATE jobs SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?""",
                (message, utcnow(), job_id),
            )
