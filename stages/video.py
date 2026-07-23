"""Video stage: HeyGen avatar video generation, polling, and download."""

from client.heygen_client import generate_avatar_video
from utils.logger import stage


def run_video_stage(audio_url: str) -> tuple[str, str]:
    """Generates the avatar video from a (publicly reachable) audio URL.

    Returns (remote_video_url, local_video_path).
    """
    if not audio_url:
        raise ValueError(
            "PUBLIC_BASE_URL is not set, so there is no public URL for HeyGen to fetch "
            "the audio from. Set it to your deployed app's origin "
            "(e.g. https://yourapp.streamlit.app). Video generation does not work "
            "against localhost, since HeyGen cannot reach your machine."
        )

    with stage("Video"):
        video_url, local_path = generate_avatar_video(audio_url)
        return video_url, str(local_path)
