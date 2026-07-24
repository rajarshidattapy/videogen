from pathlib import Path

from app.database import Database


def test_database_claims_work_once(tmp_path: Path) -> None:
    database = Database(tmp_path / "service.sqlite3")
    database.initialise()
    image_path = tmp_path / "avatar.jpg"
    image_path.write_bytes(b"test")
    database.create_avatar("avatar-1", image_path, "subject")

    avatar = database.claim_next_avatar()
    assert avatar is not None
    assert avatar["status"] == "preparing"
    assert database.claim_next_avatar() is None

    database.mark_avatar_ready("avatar-1", None)
    audio_path = tmp_path / "speech.mp3"
    audio_path.write_bytes(b"test")
    database.create_job("job-1", "avatar-1", audio_path, None)
    job = database.claim_next_job()
    assert job is not None
    assert job["status"] == "processing"
    assert database.claim_next_job() is None

