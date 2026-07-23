"""Audio stage: Sarvam speech generation, written into the app's static/ folder.

Files land in static/ (not outputs/) because Streamlit serves that folder over HTTP,
which is what gives the video stage a publicly fetchable URL to hand HeyGen.
"""

import time

from config import get_settings
from client.sarvam_client import synthesize
from utils.logger import stage


def run_audio_stage(script_text: str) -> tuple[str, str]:
    """Generates speech for the script and returns (public_url, local_path).

    public_url is "" when PUBLIC_BASE_URL is unset - playback and download still work,
    only the video stage needs the absolute URL.
    """
    settings = get_settings()

    with stage("Audio"):
        audio_bytes = synthesize(script_text)

        filename = f"speech_{int(time.time() * 1000)}.mp3"
        local_path = settings.static_dir / filename
        local_path.write_bytes(audio_bytes)

        return settings.static_file_url(filename), str(local_path)
