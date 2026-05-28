"""FastAPI auth dependencies.

Usage in a router:
    from ..utils.auth import get_current_user

    @router.get("/api/protected")
    async def protected_route(user: dict = Depends(get_current_user)):
        return {"hello": user["name"]}
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt as pyjwt

from .jwt import verify_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """Extract and verify the JWT from the Authorization header.

    Returns the decoded token payload (contains sub, email, name, picture).
    Raises 401 if missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = verify_access_token(credentials.credentials)
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict | None:
    """Like get_current_user, but returns None instead of 401 when not authenticated.

    Use for routes that work for both logged-in and anonymous users.
    """
    if credentials is None:
        return None
    try:
        return verify_access_token(credentials.credentials)
    except pyjwt.PyJWTError:
        return None
