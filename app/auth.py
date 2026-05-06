from fastapi import Header, HTTPException, status

from app.config import Settings


def validate_bearer_token(
    settings: Settings,
    authorization: str | None,
) -> None:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth scheme")

    token = authorization[len(prefix) :]
    if token != settings.auth_shared_bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def auth_dependency(
    settings: Settings,
    authorization: str | None = Header(default=None),
) -> None:
    validate_bearer_token(settings=settings, authorization=authorization)
