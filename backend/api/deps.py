"""FastAPI dependencies — authentication, settings."""

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import Settings, get_settings
from backend.core.exceptions import AuthenticationError

_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """Validate Bearer token against LAUNCHKIT_API_SECRET."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError(
            "Missing or invalid Authorization header",
            "Bearer token required",
        )

    if credentials.credentials != settings.launchkit_api_secret:
        raise AuthenticationError("Invalid API token", "The provided Bearer token is not valid")

    return credentials.credentials
