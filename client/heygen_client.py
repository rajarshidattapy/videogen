"""HeyGen avatar video generation via Composio's HTTP proxy (direct REST calls, no LLM)."""

import time
from pathlib import Path
from typing import Any

import requests

from config import get_settings
from client.composio_client import get_composio_client, get_heygen_connection_id


class HeyGenGenerationError(RuntimeError):
    pass


class HeyGenTimeoutError(RuntimeError):
    pass


def _start_generation(audio_url: str, connection_id: str, avatar_id: str) -> str:
    composio = get_composio_client()

    payload: dict[str, Any] = {
        "test": False,
        "dimension": {"width": 720, "height": 1280},
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "audio",
                    "audio_url": audio_url,
                },
                "background": {
                    "type": "color",
                    "value": "#FFFFFF",
                },
            }
        ],
    }

    response = composio.tools.proxy(
        endpoint="/v2/video/generate",
        method="POST",
        body=payload,
        connected_account_id=connection_id,
    )

    data = response.data or {}
    if data.get("error"):
        raise HeyGenGenerationError(f"HeyGen Start Error: {data['error']}")

    video_id = (data.get("data") or {}).get("video_id")
    if not video_id:
        raise HeyGenGenerationError("No Video ID received from HeyGen.")
    return video_id


def _poll_status(video_id: str, connection_id: str, interval_seconds: int, max_attempts: int) -> str:
    composio = get_composio_client()

    for _attempt in range(max_attempts):
        response = composio.tools.proxy(
            endpoint="/v1/video_status.get",
            method="GET",
            connected_account_id=connection_id,
            parameters=[{"name": "video_id", "value": video_id, "in": "query"}],
        )

        status_data = (response.data or {}).get("data")
        if not status_data:
            raise HeyGenGenerationError("Invalid status response from HeyGen")

        status = status_data.get("status")

        if status == "completed":
            video_url = status_data.get("video_url")
            if not video_url:
                raise HeyGenGenerationError("Video completed but no URL returned")
            return video_url

        if status == "failed":
            raise HeyGenGenerationError(f"Generation Failed: {status_data.get('error')}")

        time.sleep(interval_seconds)

    raise HeyGenTimeoutError(
        f"Video generation timed out after {max_attempts} attempts "
        f"({max_attempts * interval_seconds / 60:.0f} minutes). Video ID: {video_id}"
    )


def download_video(video_url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"heygen_video_{int(time.time() * 1000)}.mp4"

    with requests.get(video_url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(dest_path, "wb") as file_obj:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file_obj.write(chunk)

    return dest_path


def generate_avatar_video(audio_url: str) -> tuple[str, Path]:
    """Generates and downloads the HeyGen avatar video, returning (remote_url, local_path)."""
    settings = get_settings()

    connection_id = get_heygen_connection_id("HEYGEN")
    video_id = _start_generation(audio_url, connection_id, settings.heygen_avatar_id)
    video_url = _poll_status(
        video_id,
        connection_id,
        settings.heygen_polling_interval_seconds,
        settings.heygen_max_polling_attempts,
    )
    local_path = download_video(video_url, settings.video_output_dir)
    return video_url, local_path
