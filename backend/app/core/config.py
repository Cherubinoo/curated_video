"""Centralized application settings, loaded from environment variables / .env.

Every other module should import `settings` from here rather than reading
`os.environ` directly, so configuration stays in one auditable place.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "DSA Video Studio"
    log_level: str = "INFO"
    environment: str = "development"

    # --- Database ---
    database_url: str = "postgresql+psycopg2://dsa_studio:change_me@localhost:5432/dsa_video_studio"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- Auth ---
    api_key: str = "dev-local-admin-key-change-me"

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"

    # --- Storage ---
    storage_type: str = "local"  # local | s3 | r2
    storage_path: str = "./storage"
    public_media_base_url: str = "http://localhost:8000/media"

    # --- Rendering ---
    render_timeout_seconds: int = 600
    max_upload_size_mb: int = 50
    manim_quality: str = "medium"  # low | medium | high

    # --- Future providers (unused placeholders) ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # --- AWS Bedrock: narrative/title generation (VideoSpecificationGenerator) ---
    # A Bedrock API key (bearer token, starts "ABSK...") - Bedrock/Bedrock Runtime
    # actions only, NOT general AWS services (e.g. it cannot call Polly).
    bedrock_api_key: str = ""
    # Region for the native bedrock-runtime Converse API (boto3) - kept for
    # accounts that have normal Bedrock model access. On this project's
    # account, Converse returns "Operation not allowed" for every model in
    # every region, so the active code path uses the Mantle gateway below
    # instead (see app/services/ai/bedrock_client.py) - this field is
    # currently unused by that path.
    bedrock_region: str = "us-west-2"
    # Region for the Mantle OpenAI-compatible gateway
    # (https://bedrock-mantle.<region>.api.aws/v1/chat/completions) - this
    # is the path actually used, live-verified working with a plain bearer
    # token even while the native Converse API is blocked account-wide.
    bedrock_mantle_region: str = "us-east-1"
    bedrock_model_id: str = "deepseek.v3.2"

    # --- ElevenLabs: narration TTS (AudioService) ---
    elevenlabs_api_key: str = ""
    # "Rachel" - a standard premade ElevenLabs voice; override per taste.
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    # --- Amazon Polly: narration TTS (AudioService, preferred over ElevenLabs
    # when configured - see app/services/audio/__init__.py). Needs a real IAM
    # access key/secret (boto3's standard SigV4 credential chain) - this is
    # NOT the Bedrock API key above, which only authorizes Bedrock actions.
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    # "generative" is Polly's newest, most natural-sounding engine (a real
    # step up from "neural") - live-verified only in us-east-1/us-west-2 for
    # this account (empty voice list in ap-south-1), so the region default
    # changed to match. "Ruth" is one of the flagship generative voices.
    polly_region: str = "us-east-1"
    polly_voice_id: str = "Ruth"
    polly_engine: str = "generative"

    # --- Rate limiting ---
    rate_limit_mutations: str = "20/minute"

    @property
    def storage_root(self) -> Path:
        return Path(self.storage_path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
