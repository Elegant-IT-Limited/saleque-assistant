"""Runtime settings, read once from the environment (or a local .env file).

Everything the service needs from the outside world is declared here. The database
URL and the session secret have no defaults, so a missing or weak value stops the
process at startup instead of on the first request that happens to need it.
"""

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    session_secret: SecretStr

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    typesafe_api_key: SecretStr | None = None

    # Claude answers first; OpenAI takes over on an outage (see app/integrations/ai_provider.py).
    claude_model: str = "claude-sonnet-5"
    openai_model: str = "gpt-5-mini"
    embedding_model: str = "text-embedding-3-small"
    jev_model: str = "jev-1.13"

    @field_validator("session_secret")
    @classmethod
    def _long_enough(cls, v: SecretStr) -> SecretStr:
        # anyone who can guess this can sign a session for any workspace
        if len(v.get_secret_value()) < 32:
            raise ValueError("SESSION_SECRET must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
