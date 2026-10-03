"""Supabase email authentication and Google OpenID Connect login.

Supabase owns email/password verification and confirmation. After Supabase (or
Google) proves an identity, HydraClip synchronizes a minimal local user row and
issues its existing first-party token pair so every protected API keeps one
authorization contract.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.models import User
from apps.api.services.auth import hash_password
from apps.api.services.crypto import DecryptionError, seal_state, unseal_state


class ExternalAuthError(RuntimeError):
    """A configured identity provider rejected or could not complete a flow."""


class ExternalAuthNotConfigured(ExternalAuthError):
    """The requested identity provider is missing deployment settings."""


@dataclass(frozen=True)
class IdentityProfile:
    email: str
    name: str | None = None
    email_verified: bool = True
    provider_id: str | None = None


def supabase_configuration_error() -> str | None:
    if not settings.SUPABASE_URL:
        return "SUPABASE_URL (or PROJECT_URL) is not configured"
    if not settings.SUPABASE_ANON_KEY:
        return "SUPABASE_ANON_KEY (or SUPABASE_PUBLISHABLE_KEY) is not configured"
    return None


def google_configuration_error() -> str | None:
    if not settings.YOUTUBE_CLIENT_ID:
        return "YOUTUBE_CLIENT_ID is not configured"
    if not settings.YOUTUBE_CLIENT_SECRET:
        return "YOUTUBE_CLIENT_SECRET is not configured"
    if not settings.GOOGLE_LOGIN_REDIRECT_URI:
        return "GOOGLE_LOGIN_REDIRECT_URI is not configured"
    return None


def _provider_message(response: httpx.Response, fallback: str) -> str:
    try:
        body = response.json()
    except ValueError:
        return fallback
    if isinstance(body, dict):
        for key in ("msg", "message", "error_description", "error"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
    return fallback


def _supabase_headers(*, access_token: str | None = None) -> dict[str, str]:
    key = settings.SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {access_token or key}",
        "Content-Type": "application/json",
    }


async def supabase_password_login(
    email: str,
    password: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    problem = supabase_configuration_error()
    if problem:
        raise ExternalAuthNotConfigured(problem)

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS)
    try:
        response = await client.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token",
            params={"grant_type": "password"},
            headers=_supabase_headers(),
            json={"email": email.strip().lower(), "password": password},
        )
    except httpx.HTTPError as exc:
        raise ExternalAuthError(f"Supabase Auth is unreachable ({type(exc).__name__}).") from exc
    finally:
        if owns_client:
            await client.aclose()

    if not response.is_success:
        raise ExternalAuthError(_provider_message(response, "Supabase rejected the login."))
    payload = response.json()
    if not payload.get("access_token"):
        raise ExternalAuthError("Supabase returned no access token.")
    return payload


async def supabase_signup(
    email: str,
    password: str,
    name: str | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    problem = supabase_configuration_error()
    if problem:
        raise ExternalAuthNotConfigured(problem)

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS)
    try:
        response = await client.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/signup",
            headers=_supabase_headers(),
            json={
                "email": email.strip().lower(),
                "password": password,
                "data": {"name": name} if name else {},
            },
        )
    except httpx.HTTPError as exc:
        raise ExternalAuthError(f"Supabase Auth is unreachable ({type(exc).__name__}).") from exc
    finally:
        if owns_client:
            await client.aclose()

    if not response.is_success:
        raise ExternalAuthError(_provider_message(response, "Supabase rejected the signup."))
    return response.json()


async def supabase_user(
    access_token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> IdentityProfile:
    problem = supabase_configuration_error()
    if problem:
        raise ExternalAuthNotConfigured(problem)

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS)
    try:
        response = await client.get(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
            headers=_supabase_headers(access_token=access_token),
        )
    except httpx.HTTPError as exc:
        raise ExternalAuthError(f"Supabase Auth is unreachable ({type(exc).__name__}).") from exc
    finally:
        if owns_client:
            await client.aclose()

    if not response.is_success:
        raise ExternalAuthError(_provider_message(response, "Supabase session is invalid."))
    body = response.json()
    email = str(body.get("email") or "").strip().lower()
    if not email:
        raise ExternalAuthError("Supabase returned a user without an email address.")
    metadata = body.get("user_metadata") or {}
    name = metadata.get("name") or metadata.get("full_name")
    verified = bool(body.get("email_confirmed_at") or body.get("confirmed_at"))
    return IdentityProfile(
        email=email,
        name=str(name) if name else None,
        email_verified=verified,
        provider_id=str(body.get("id") or "") or None,
    )


def google_authorize_url() -> str:
    problem = google_configuration_error()
    if problem:
        raise ExternalAuthNotConfigured(problem)
    state = seal_state({"purpose": "google_login", "nonce": secrets.token_urlsafe(24)})
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )


async def google_identity(
    code: str,
    state: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> IdentityProfile:
    problem = google_configuration_error()
    if problem:
        raise ExternalAuthNotConfigured(problem)
    try:
        state_payload = unseal_state(state, settings.OAUTH_STATE_TTL_SECONDS)
    except DecryptionError as exc:
        raise ExternalAuthError(str(exc)) from exc
    if state_payload.get("purpose") != "google_login":
        raise ExternalAuthError("The Google login state is invalid.")

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0)
    try:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if not token_response.is_success:
            raise ExternalAuthError(
                _provider_message(token_response, "Google rejected the login code.")
            )
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise ExternalAuthError("Google returned no access token.")
        user_response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    except httpx.HTTPError as exc:
        raise ExternalAuthError(f"Google login is unreachable ({type(exc).__name__}).") from exc
    finally:
        if owns_client:
            await client.aclose()

    if not user_response.is_success:
        raise ExternalAuthError(_provider_message(user_response, "Google user lookup failed."))
    body = user_response.json()
    email = str(body.get("email") or "").strip().lower()
    if not email:
        raise ExternalAuthError("Google returned an account without an email address.")
    if body.get("email_verified") is False:
        raise ExternalAuthError("Google has not verified this email address.")
    return IdentityProfile(
        email=email,
        name=str(body.get("name") or "") or None,
        email_verified=True,
        provider_id=str(body.get("sub") or "") or None,
    )


def sync_local_user(db: Session, profile: IdentityProfile) -> User:
    """Create/update the local authorization record for a verified identity."""
    user = db.scalar(select(User).where(func.lower(User.email) == profile.email))
    if user is None:
        # External-auth users cannot use the legacy local-password endpoint.
        user = User(
            email=profile.email,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            name=profile.name,
            role="USER",
            is_active=True,
            is_verified=profile.email_verified,
        )
        db.add(user)
    else:
        # An identity provider proving the email again must never undo an
        # administrator's explicit deactivation decision.
        if not user.is_active:
            raise ExternalAuthError("This HydraClip account has been deactivated.")
        user.is_verified = user.is_verified or profile.email_verified
        if profile.name and not user.name:
            user.name = profile.name
    db.commit()
    db.refresh(user)
    return user
