"""Google OAuth authentication endpoints.

Flow:
1. Frontend gets a Google credential (ID token) via @react-oauth/google
2. POST /api/auth/google sends { credential: "..." }
3. Backend verifies the ID token with Google, creates/updates the user,
   and returns a JWT + user profile.

Users are persisted to Postgres when DATABASE_URL is configured.
Falls back to in-memory store if DB is unavailable.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from ..config import settings
from ..utils.jwt import create_access_token
from ..utils.db import get_pool

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory fallback user store (used when DB is unavailable)
_users: dict[str, dict] = {}


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    token: str
    user: dict


@router.post("/api/auth/google", response_model=AuthResponse)
async def google_login(body: GoogleLoginRequest):
    """Verify Google ID token and return a JWT."""
    try:
        idinfo = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as e:
        logger.warning("Google token verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Google token")

    # Extract user info from the verified token
    google_id = idinfo["sub"]
    email = idinfo.get("email", "")
    name = idinfo.get("name", "")
    picture = idinfo.get("picture", "")

    user = {
        "id": google_id,
        "email": email,
        "name": name,
        "picture": picture,
    }

    # Upsert to Postgres if available
    pool = await get_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (id, email, name, picture, created_at, last_login)
                    VALUES ($1, $2, $3, $4, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE
                        SET email      = EXCLUDED.email,
                            name       = EXCLUDED.name,
                            picture    = EXCLUDED.picture,
                            last_login = NOW()
                    """,
                    google_id, email, name, picture,
                )
        except Exception as e:
            logger.warning("DB upsert failed for user %s: %s", email, e)
            # Fall through to in-memory fallback
            _users[google_id] = user
    else:
        # In-memory fallback
        _users[google_id] = user

    # Create JWT (embeds all user info so no DB read needed for auth checks)
    token = create_access_token({
        "sub": google_id,
        "email": email,
        "name": name,
        "picture": picture,
    })

    return AuthResponse(token=token, user=user)


@router.get("/api/users/me")
async def get_current_user_profile():
    """Placeholder — actual auth check happens via dependency injection."""
    return {"message": "Use the auth dependency to get user info"}
