"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """LaunchKit configuration — all values from env / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    linkedin_access_token: str = Field(default="", alias="LINKEDIN_ACCESS_TOKEN")
    launchkit_api_secret: str = Field(default="change-me", alias="LAUNCHKIT_API_SECRET")
    environment: Literal["development", "production"] = Field(
        default="development", alias="ENVIRONMENT"
    )

    gemini_model: str = "gemini-2.0-flash"
    api_v1_prefix: str = "/api/v1"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
