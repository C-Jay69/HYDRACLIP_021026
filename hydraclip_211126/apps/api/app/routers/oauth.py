"""OAuth Router."""

import urllib.parse
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, create_access_token, decode_token
from app.models.user import User
from app.models.social import SocialAccount, PlatformToken
from app.core.encryption import encrypt_token
from app.config import get_settings
import secrets

settings = get_settings()

router = APIRouter(prefix="/oauth", tags=["oauth"])


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from token."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/youtube/connect")
async def youtube_connect(
    user: User = Depends(get_current_user),
):
    """Initiate YouTube OAuth flow."""
    # A short-lived signed token identifies the user in the callback and
    # protects the flow against CSRF/state tampering.
    state = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=15),
        purpose="youtube_oauth",
    )

    params = urllib.parse.urlencode(
        {
            "client_id": settings.youtube_client_id,
            "redirect_uri": settings.youtube_redirect_uri,
            "response_type": "code",
            "scope": (
                "https://www.googleapis.com/auth/youtube.upload "
                "https://www.googleapis.com/auth/youtube.readonly"
            ),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return {"auth_url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}


@router.get("/youtube/callback")
async def youtube_callback(
    code: str,
    state: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle YouTube OAuth callback."""
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    try:
        state_payload = decode_token(state)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    if state_payload.get("purpose") != "youtube_oauth":
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    user_id = state_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    # Exchange code for tokens
    import httpx
    
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.youtube_client_id,
        "client_secret": settings.youtube_client_secret,
        "redirect_uri": settings.youtube_redirect_uri,
        "grant_type": "authorization_code",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        tokens = response.json()
    
    if "error" in tokens:
        raise HTTPException(status_code=400, detail=f"OAuth error: {tokens['error']}")
    
    # Get user info from YouTube
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user_data = user_response.json()
    
    channel_name = "YouTube Channel"
    channel_id = None
    if "items" in user_data and user_data["items"]:
        channel_name = user_data["items"][0]["snippet"]["title"]
        channel_id = user_data["items"][0]["id"]
    
    # Store social account
    import secrets
    account = SocialAccount(
        id=secrets.token_urlsafe(16),
        user_id=user_id,
        platform="youtube",
        account_name=channel_name,
        account_id=channel_id,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    
    # Store encrypted tokens
    token = PlatformToken(
        id=secrets.token_urlsafe(16),
        social_account_id=account.id,
        access_token_encrypted=encrypt_token(tokens["access_token"]),
        refresh_token_encrypted=encrypt_token(tokens.get("refresh_token", "")),
        token_type=tokens.get("token_type", "Bearer"),
        scope=tokens.get("scope", ""),
    )
    db.add(token)
    await db.commit()
    
    # Redirect to app
    return RedirectResponse(url=f"{settings.app_url}/connect?success=youtube")


@router.delete("/{platform}/disconnect")
async def disconnect_platform(
    platform: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a social platform."""
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == user.id,
            SocialAccount.platform == platform,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    await db.delete(account)
    await db.commit()
    
    return {"success": True, "message": f"Disconnected {platform}"}