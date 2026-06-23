"""Custom exceptions and global error handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class LaunchKitError(Exception):
    """Base exception for LaunchKit domain errors."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        self.message = message
        self.detail = detail or message
        super().__init__(message)


class NotFoundError(LaunchKitError):
    """Resource not found."""


class ValidationError(LaunchKitError):
    """Input validation failed."""


class AuthenticationError(LaunchKitError):
    """Invalid or missing API credentials."""


class GeminiError(LaunchKitError):
    """Gemini API call failed after retries."""

    def __init__(self, message: str, detail: str | None = None, original: Exception | None = None):
        super().__init__(message, detail)
        self.original = original


class SupabaseError(LaunchKitError):
    """Supabase operation failed."""


class GitHubError(LaunchKitError):
    """GitHub API operation failed."""


class AgentError(LaunchKitError):
    """Agent execution failed."""


def register_exception_handlers(app: FastAPI) -> None:
    """Register structured JSON error responses for all exception types."""

    @app.exception_handler(LaunchKitError)
    async def launchkit_error_handler(_request: Request, exc: LaunchKitError) -> JSONResponse:
        status_code = _status_for(exc)
        return JSONResponse(
            status_code=status_code,
            content={"error": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        from backend.config import get_settings

        settings = get_settings()
        detail = str(exc) if settings.is_development else "An unexpected error occurred"
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": detail},
        )


def _status_for(exc: LaunchKitError) -> int:
    mapping: dict[type[LaunchKitError], int] = {
        NotFoundError: 404,
        ValidationError: 422,
        AuthenticationError: 401,
        GeminiError: 502,
        SupabaseError: 503,
        GitHubError: 502,
        AgentError: 500,
    }
    for exc_type, code in mapping.items():
        if isinstance(exc, exc_type):
            return code
    return 500
