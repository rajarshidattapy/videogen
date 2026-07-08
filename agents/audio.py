"""Audio stage: ElevenLabs speech generation and local file storage."""

import time

import requests

from config import get_settings
from services.elevenlabs_client import generate_speech
from utils.logger import stage


def run_audio_stage(script_text: str) -> tuple[str, str]:
    """Generates speech for the script, downloads it locally, and returns (remote_url, local_path)."""
    settings = get_settings()

    with stage("Audio"):
        audio_url = generate_speech(script_text)

        local_path = settings.audio_output_dir / f"speech_{int(time.time() * 1000)}.mp3"
        response = requests.get(audio_url, timeout=60)
        response.raise_for_status()
        local_path.write_bytes(response.content)

        return audio_url, str(local_path)
