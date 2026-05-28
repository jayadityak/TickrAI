"""JWT creation and verification utilities."""

from datetime import datetime, timedelta, timezone

import jwt

from ..config import settings


def create_access_token(data: dict) -> str:
    """Create a JWT access token with an expiry."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days)
    payload.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> dict:
    """Verify and decode a JWT access token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
