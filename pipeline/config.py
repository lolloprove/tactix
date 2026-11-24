from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env.local"), extra="ignore")

    supabase_url: str | None = None
    supabase_service_role_key: SecretStr | None = None

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_delay_s: float = 4.5

    football_api_key: SecretStr | None = None
    football_api_provider: Literal["football_data", "api_football"] = "football_data"

    season: str = "2026/27"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
