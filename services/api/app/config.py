"""Settings. Every secret comes from the environment, never from the database or the browser."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../../.env", ".env", "../../.env.secrets", ".env.secrets"), extra="ignore")

    app_env: Literal["local", "test", "production"] = "local"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    database_url: str = "sqlite:///./data/app.db"

    # Optional shared secret for deployed environments. Required when app_env == production.
    api_auth_token: SecretStr | None = None

    # Fernet key for encrypting Instagram tokens at rest. Generate with scripts/gen_key.py.
    token_encryption_key: SecretStr | None = None

    # Agent execution: mock | bedrock | openai | anthropic | ollama | agentcore
    agent_mode: Literal["mock", "bedrock", "openai", "anthropic", "ollama", "agentcore"] = "mock"
    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    bedrock_model_id: str | None = None
    bedrock_max_tokens: int = 2000
    agent_timeout_seconds: int = 90
    agent_max_concurrency: int = 2
    agent_max_model_calls: int = 8
    agentcore_runtime_arn: str | None = None
    # Direct model APIs (keys stay server-side; never sent to the browser)
    openai_api_key: SecretStr | None = None
    openai_model_id: str | None = None
    # Any OpenAI-compatible API (free tiers: Google Gemini, Groq, OpenRouter). Empty = api.openai.com
    openai_base_url: str | None = None
    # Free local models on this Mac via Ollama (no key, nothing leaves the machine)
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model_id: str = "llama3.2"
    anthropic_api_key: SecretStr | None = None
    anthropic_model_id: str = "claude-sonnet-5-5"
    model_max_tokens: int = 2000

    # Meta: Instagram API with Instagram Login
    meta_app_id: str | None = None
    meta_app_secret: SecretStr | None = None
    meta_redirect_uri: str = "http://localhost:8000/api/instagram/callback"
    meta_scopes: str = Field(
        default="instagram_business_basic,instagram_business_manage_insights,"
        "instagram_business_content_publish,instagram_business_manage_comments"
    )
    instagram_graph_base: str = "https://graph.instagram.com"
    instagram_api_version: str = "v23.0"

    # Optional public media hosting for publishing
    s3_media_bucket: str | None = None

    # Optional research provider (Tavily-compatible JSON search API)
    research_api_url: str | None = None
    research_api_key: SecretStr | None = None

    enable_local_scheduler: bool = True  # reminders only; never publishes

    @property
    def instagram_configured(self) -> bool:
        return bool(self.meta_app_id and self.meta_app_secret and self.token_encryption_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
