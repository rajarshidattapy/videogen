"""Sarvam AI text-to-speech - a direct REST call, no Composio broker and no LLM agent.

Unlike the ElevenLabs path this replaced, Sarvam returns base64 audio rather than a
hosted URL, so callers get raw bytes and decide where to put them.
"""

import base64

import requests

from config import get_settings

TTS_ENDPOINT = "https://api.sarvam.ai/text-to-speech"

# Per-request text limits from the Sarvam docs, keyed by model.
_MAX_CHARS = {"bulbul:v2": 1500, "bulbul:v3": 2500}


class SarvamError(RuntimeError):
    pass


def synthesize(script_text: str) -> bytes:
    """Converts the script to speech and returns MP3 bytes."""
    settings = get_settings()

    text = script_text.strip()
    if not text:
        raise SarvamError("Cannot generate speech from an empty script.")

    # ponytail: single request only. Split on sentence boundaries and concatenate
    # if scripts ever need to exceed the model's per-request limit.
    limit = _MAX_CHARS.get(settings.sarvam_model, 1500)
    if len(text) > limit:
        raise SarvamError(
            f"Script is {len(text)} characters; {settings.sarvam_model} accepts at most "
            f"{limit} per request. Shorten the script and retry."
        )

    response = requests.post(
        TTS_ENDPOINT,
        headers={"api-subscription-key": settings.sarvam_api_key},
        json={
            "text": text,
            "target_language_code": settings.sarvam_language,
            "model": settings.sarvam_model,
            "speaker": settings.sarvam_speaker,
            "output_audio_codec": "mp3",
        },
        timeout=120,
    )

    if response.status_code != 200:
        raise SarvamError(f"Sarvam TTS failed ({response.status_code}): {response.text[:300]}")

    audios = (response.json() or {}).get("audios") or []
    if not audios:
        raise SarvamError("Sarvam returned no audio for this script.")

    return b"".join(base64.b64decode(chunk) for chunk in audios)
