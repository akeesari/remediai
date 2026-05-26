from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.config.settings import get_settings

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """Validate Bearer token. No-ops when api_bearer_token is empty (local dev)."""
    expected = get_settings().api_bearer_token.get_secret_value()
    if not expected:
        return  # auth disabled — local dev or explicit opt-out
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
