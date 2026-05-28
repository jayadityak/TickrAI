"""Google OAuth authentication endpoints.

Flow:
1. Frontend gets a Google credential (ID token) via @react-oauth/google
2. POST /api/auth/google sends { credential: "..." }
3. Backend verifies the ID token with Google, creates/updates the user,
   and returns a JWT + user profile.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from ..config import settings
from ..utils.jwt import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory user store (replace with DB later)
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

    # Upsert user in memory store
    user = {
        "id": google_id,
        "email": email,
        "name": name,
        "picture": picture,
    }
    _users[google_id] = user

    # Create JWT
    token = create_access_token({"sub": google_id, "email": email, "name": name, "picture": picture})

    return AuthResponse(token=token, user=user)


@router.get("/api/users/me")
async def get_current_user():
    """Placeholder — actual auth check happens via dependency injection."""
    # This will be protected by the auth dependency
    return {"message": "Use the auth dependency to get user info"}
