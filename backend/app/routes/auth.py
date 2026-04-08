"""
Authentication endpoints — Supabase-compatible JWT pattern.
Edge auth is handled by Cloudflare Worker; this handles token issuance.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticate user and issue JWT pair."""
    # TODO: Implement actual auth against Supabase/local DB
    raise HTTPException(status_code=501, detail="Auth not yet implemented")


@router.post("/register")
async def register(req: LoginRequest):
    """Register a new user account."""
    # TODO: Implement registration
    raise HTTPException(status_code=501, detail="Registration not yet implemented")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token():
    """Refresh an expired access token."""
    # TODO: Implement token refresh
    raise HTTPException(status_code=501, detail="Token refresh not yet implemented")
