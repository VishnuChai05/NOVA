from fastapi import Header, HTTPException, status

from app.core.settings import settings


def require_operational_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.api_auth_enabled:
        return

    expected = (settings.operational_api_key or "").strip()
    if not expected or expected == "change-me":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational API key is not configured",
        )

    if not x_api_key or x_api_key.strip() != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
