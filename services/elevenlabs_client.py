"""ElevenLabs text-to-speech, brokered through a Composio MCP session + OpenAI agent."""

from config import get_settings
from services.composio_client import create_toolkit_session
from services.openai_client import build_agent, run_agent
from utils.helpers import extract_first_url
from utils.prompts import voice_director_instructions


class ElevenLabsAuthPendingError(RuntimeError):
    """Raised when Composio returns an auth link instead of a generated audio URL."""


def generate_speech(script_text: str) -> str:
    """Generates speech for the script and returns the hosted audio URL."""
    settings = get_settings()

    session = create_toolkit_session(["elevenlabs"], settings.elevenlabs_auth_config_id)
    agent = build_agent(
        name="Voice Director",
        instructions=voice_director_instructions(settings.elevenlabs_voice_id, settings.elevenlabs_model_id),
        session=session,
    )

    raw_output = run_agent(agent, f'Generate audio for this script: \n"{script_text}"')

    url = extract_first_url(raw_output)
    if url and "connect.composio.dev" in url:
        raise ElevenLabsAuthPendingError(
            f"ElevenLabs authentication pending. Please authenticate using this link and retry: {url}"
        )

    return url or raw_output
