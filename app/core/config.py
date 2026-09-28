"""Runtime settings, read once from the environment (or a local .env file).

Everything the service needs from the outside world is declared here, so a missing
key fails at startup instead of on the first request that happens to need it.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    session_secret: SecretStr = SecretStr("change-me")

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    typesafe_api_key: SecretStr | None = None

    # Claude answers first; OpenAI takes over on an outage (see app/integrations/ai_provider.py).
    claude_model: str = "claude-sonnet-5"
    openai_model: str = "gpt-5-mini"
    embedding_model: str = "text-embedding-3-small"
    jev_model: str = "jev-1.13"


@lru_cache
def get_settings() -> Settings:
    return Settings()
