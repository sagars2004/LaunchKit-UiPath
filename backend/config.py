"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["gemini", "nvidia"]


class Settings(BaseSettings):
    """LaunchKit configuration — all values from env / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM provider selection
    llm_provider: str = Field(default="", alias="LLM_PROVIDER")

    # Google Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    gemini_fallback_model: str = Field(default="gemini-1.5-flash", alias="GEMINI_FALLBACK_MODEL")

    # NVIDIA NIM (build.nvidia.com) — OpenAI-compatible API
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_model: str = Field(
        default="meta/llama-3.3-70b-instruct",
        alias="NVIDIA_MODEL",
    )
    nvidia_fallback_model: str = Field(
        default="meta/llama-3.1-8b-instruct",
        alias="NVIDIA_FALLBACK_MODEL",
    )
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        alias="NVIDIA_BASE_URL",
    )

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    linkedin_access_token: str = Field(default="", alias="LINKEDIN_ACCESS_TOKEN")
    launchkit_api_secret: str = Field(default="", alias="LAUNCHKIT_API_SECRET")
    environment: Literal["development", "production"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    api_v1_prefix: str = "/api/v1"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def resolved_llm_provider(self) -> LLMProvider:
        """Pick provider from LLM_PROVIDER env, or auto-detect from available keys."""
        explicit = self.llm_provider.strip().lower()
        if explicit in ("gemini", "nvidia"):
            return explicit  # type: ignore[return-value]
        if self.nvidia_api_key:
            return "nvidia"
        if self.gemini_api_key:
            return "gemini"
        return "nvidia"

    @property
    def resolved_llm_model(self) -> str:
        if self.resolved_llm_provider == "nvidia":
            return self.nvidia_model
        return self.gemini_model

    @property
    def resolved_llm_fallback_model(self) -> str:
        if self.resolved_llm_provider == "nvidia":
            return self.nvidia_fallback_model
        return self.gemini_fallback_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
