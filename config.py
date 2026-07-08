"""Application configuration, loaded and validated from environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OpenAI
    openai_api_key: str = Field(validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", validation_alias="OPENAI_MODEL")

    # Composio
    composio_api_key: str = Field(validation_alias="COMPOSIO_API_KEY")
    composio_user_id: str = Field(default="default-user", validation_alias="COMPOSIO_USER_ID")

    # Auth config IDs (from the Composio dashboard) - optional, toolkits fall back
    # to the user's default connected account when omitted.
    youtube_auth_config_id: str | None = Field(default=None, validation_alias="YOUTUBE_AUTH_CONFIG_ID")
    twitter_auth_config_id: str | None = Field(default=None, validation_alias="TWITTER_AUTH_CONFIG_ID")
    exa_auth_config_id: str | None = Field(default=None, validation_alias="EXA_AUTH_CONFIG_ID")
    elevenlabs_auth_config_id: str | None = Field(default=None, validation_alias="ELEVENLABS_AUTH_CONFIG_ID")
    heygen_auth_config_id: str | None = Field(default=None, validation_alias="HEYGEN_AUTH_CONFIG_ID")

    # ElevenLabs
    elevenlabs_voice_id: str = Field(default="EIsgvJT3rwoPvRFG6c4n", validation_alias="ELEVENLABS_VOICE_ID")
    elevenlabs_model_id: str = Field(default="eleven_multilingual_v2", validation_alias="ELEVENLABS_MODEL_ID")

    # HeyGen
    heygen_avatar_id: str = Field(default="109cdee34a164003b0e847ffce93828e", validation_alias="HEYGEN_AVATAR_ID")
    heygen_polling_interval_seconds: int = Field(default=15, validation_alias="HEYGEN_POLLING_INTERVAL_SECONDS")
    heygen_max_polling_attempts: int = Field(default=60, validation_alias="HEYGEN_MAX_POLLING_ATTEMPTS")

    # Storage
    output_dir: Path = BASE_DIR / "outputs"
    audio_output_dir: Path = BASE_DIR / "outputs" / "audio"
    video_output_dir: Path = BASE_DIR / "outputs" / "videos"
    log_dir: Path = BASE_DIR / "logs"

    def ensure_output_dirs(self) -> None:
        for directory in (self.output_dir, self.audio_output_dir, self.video_output_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Returns the process-wide singleton Settings instance, validating env vars on first access."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_output_dirs()
    return _settings
