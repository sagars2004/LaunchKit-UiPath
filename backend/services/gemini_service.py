"""Backward-compatible re-exports — use llm_service.py instead."""

from backend.services.llm_service import (
    GeminiService,
    LLMService,
    get_gemini_service,
    get_llm_service,
)

__all__ = ["GeminiService", "LLMService", "get_gemini_service", "get_llm_service"]
