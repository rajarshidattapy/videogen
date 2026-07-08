"""Video stage: HeyGen avatar video generation, polling, and download."""

from services.heygen_client import generate_avatar_video
from utils.logger import stage


def run_video_stage(audio_url: str) -> tuple[str, str]:
    """Generates the avatar video from a (publicly reachable) audio URL.

    Returns (remote_video_url, local_video_path).
    """
    with stage("Video"):
        video_url, local_path = generate_avatar_video(audio_url)
        return video_url, str(local_path)
