"""Unified LLM service — supports Google Gemini and NVIDIA NIM (build.nvidia.com)."""

import asyncio
import json
import logging
import random
import re
from typing import Any, TypeVar

import google.generativeai as genai
import httpx
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel, ValidationError

from backend.config import Settings, get_settings
from backend.core.exceptions import LLMError

logger = logging.getLogger("launchkit.llm")

T = TypeVar("T", bound=BaseModel)

_GEMINI_RETRYABLE = (
    google_exceptions.ResourceExhausted,
    google_exceptions.ServiceUnavailable,
    google_exceptions.InternalServerError,
    google_exceptions.DeadlineExceeded,
)
_HTTP_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_DELAY = 1.0
_NVIDIA_DEFAULT_BASE = "https://integrate.api.nvidia.com/v1"


class LLMService:
    """Single entry point for all LLM inference (Gemini or NVIDIA NIM)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = self.settings.resolved_llm_provider
        self.model_name = self.settings.resolved_llm_model
        self.fallback_model_name = self.settings.resolved_llm_fallback_model
        self._gemini_models: dict[str, genai.GenerativeModel] = {}

        if self.provider == "gemini":
            if not self.settings.gemini_api_key:
                raise LLMError("Gemini not configured", "Set GEMINI_API_KEY in .env")
            genai.configure(api_key=self.settings.gemini_api_key)
        elif self.provider == "nvidia":
            if not self.settings.nvidia_api_key:
                raise LLMError("NVIDIA NIM not configured", "Set NVIDIA_API_KEY in .env")
        else:
            raise LLMError("Unknown LLM provider", f"LLM_PROVIDER={self.provider}")

        logger.info("LLM provider=%s model=%s", self.provider, self.model_name)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        if self.provider == "nvidia":
            return await self._nvidia_generate_text(prompt, system_prompt, temperature)
        return await self._gemini_generate_text(prompt, system_prompt, temperature)

    async def generate_structured(
        self,
        prompt: str,
        output_schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> T:
        schema_hint = json.dumps(output_schema.model_json_schema(), indent=2)
        enriched_system = (system_prompt or "") + (
            f"\n\nRespond with valid JSON matching this schema:\n{schema_hint}"
        )
        if self.provider == "nvidia":
            raw = await self._nvidia_generate_text(
                prompt, enriched_system, temperature, json_mode=True
            )
        else:
            raw = await self._gemini_generate_raw(
                prompt, enriched_system, temperature, json_mode=True
            )

        try:
            data = json.loads(_extract_json(raw))
            return output_schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMError(
                "Failed to parse structured response",
                str(exc),
                original=exc,
            ) from exc

    # ── Gemini ────────────────────────────────────────────────────────────────

    async def _gemini_generate_text(
        self, prompt: str, system_prompt: str | None, temperature: float
    ) -> str:
        raw = await self._gemini_generate_raw(prompt, system_prompt, temperature, json_mode=False)
        if not raw:
            raise LLMError("Empty response from LLM", "Model returned no text")
        return raw.strip()

    async def _gemini_generate_raw(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        json_mode: bool,
    ) -> str:
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        config = genai.GenerationConfig(**config_kwargs)
        contents = _build_gemini_contents(prompt, system_prompt)
        response = await self._gemini_call_with_retry(contents, config)
        self._log_gemini_usage(response)
        return response.text or ""

    def _get_gemini_model(self, model_name: str) -> genai.GenerativeModel:
        if model_name not in self._gemini_models:
            self._gemini_models[model_name] = genai.GenerativeModel(model_name)
        return self._gemini_models[model_name]

    async def _gemini_call_with_retry(
        self,
        contents: list,
        config: genai.GenerationConfig,
        model_name: str | None = None,
    ):
        model_name = model_name or self.model_name
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                model = self._get_gemini_model(model_name)
                return await model.generate_content_async(contents, generation_config=config)
            except google_exceptions.ResourceExhausted as exc:
                last_error = exc
                if model_name == self.model_name and self.fallback_model_name:
                    logger.warning(
                        "Gemini quota hit for %s, trying fallback %s",
                        model_name,
                        self.fallback_model_name,
                    )
                    try:
                        fallback = self._get_gemini_model(self.fallback_model_name)
                        return await fallback.generate_content_async(
                            contents, generation_config=config
                        )
                    except Exception as fallback_exc:
                        last_error = fallback_exc
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BASE_DELAY * (2**attempt) + random.uniform(0, 0.5))
            except _GEMINI_RETRYABLE as exc:
                last_error = exc
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BASE_DELAY * (2**attempt) + random.uniform(0, 0.5))
            except Exception as exc:
                raise LLMError("Gemini API call failed", str(exc), original=exc) from exc

        raise LLMError(
            "Gemini API failed after retries",
            _format_quota_message(last_error, "gemini"),
            original=last_error,
        )

    def _log_gemini_usage(self, response) -> None:
        if not self.settings.is_development:
            return
        usage = getattr(response, "usage_metadata", None)
        if usage:
            logger.info(
                "LLM tokens (gemini) — prompt: %s, output: %s, total: %s",
                getattr(usage, "prompt_token_count", "?"),
                getattr(usage, "candidates_token_count", "?"),
                getattr(usage, "total_token_count", "?"),
            )

    # ── NVIDIA NIM ────────────────────────────────────────────────────────────

    async def _nvidia_generate_text(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        json_mode: bool = False,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 8192,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        data = await self._nvidia_post("/chat/completions", payload)
        self._log_nvidia_usage(data)

        choices = data.get("choices") or []
        if not choices:
            raise LLMError("Empty response from NVIDIA NIM", "No choices in response")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise LLMError("Empty response from NVIDIA NIM", "Model returned no text")
        return content.strip()

    async def _nvidia_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.nvidia_base_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.settings.nvidia_api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code in _HTTP_RETRYABLE and attempt < _MAX_RETRIES - 1:
                        delay = _BASE_DELAY * (2**attempt) + random.uniform(0, 0.5)
                        logger.warning(
                            "NVIDIA retry %d/%d after HTTP %s (%.1fs)",
                            attempt + 1,
                            _MAX_RETRIES,
                            response.status_code,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in _HTTP_RETRYABLE and attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BASE_DELAY * (2**attempt))
                    continue
                detail = exc.response.text[:500] if exc.response else str(exc)
                raise LLMError(
                    f"NVIDIA API error (HTTP {exc.response.status_code})",
                    detail,
                    original=exc,
                ) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BASE_DELAY * (2**attempt))
                    continue
                raise LLMError("NVIDIA API call failed", str(exc), original=exc) from exc

        raise LLMError(
            "NVIDIA API failed after retries",
            _format_quota_message(last_error, "nvidia"),
            original=last_error,
        )

    def _log_nvidia_usage(self, data: dict[str, Any]) -> None:
        if not self.settings.is_development:
            return
        usage = data.get("usage") or {}
        if usage:
            logger.info(
                "LLM tokens (nvidia) — prompt: %s, output: %s, total: %s",
                usage.get("prompt_tokens", "?"),
                usage.get("completion_tokens", "?"),
                usage.get("total_tokens", "?"),
            )


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
    return text


def _build_gemini_contents(prompt: str, system_prompt: str | None) -> list:
    if system_prompt:
        return [
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ["Understood. I will follow those instructions."]},
            {"role": "user", "parts": [prompt]},
        ]
    return prompt


def _format_quota_message(exc: Exception | None, provider: str) -> str:
    if exc is None:
        return f"Unknown {provider} error"
    text = str(exc)
    if "quota" in text.lower() or "429" in text or "ResourceExhausted" in type(exc).__name__:
        if provider == "gemini":
            return (
                "Gemini API quota exceeded. Set GEMINI_MODEL=gemini-1.5-flash or "
                "LLM_PROVIDER=nvidia. See https://ai.dev/rate-limit"
            )
        return (
            "NVIDIA NIM rate limit hit. Wait a minute and retry, or pick a smaller model. "
            "See https://build.nvidia.com/"
        )
    return text


def get_llm_service(settings: Settings | None = None) -> LLMService:
    return LLMService(settings)


# Backward-compatible aliases
GeminiService = LLMService
get_gemini_service = get_llm_service
