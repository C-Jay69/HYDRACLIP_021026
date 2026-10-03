"""Connecting, listing and disconnecting publishing accounts.

The callback path here must match the redirect URI registered with each
provider. These routes live at ``/oauth/{platform}/callback``.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

from apps.api.core.config import settings
from apps.api.core.deps import CurrentUser, DbSession
from apps.api.schemas.social import AuthorizeUrl, PlatformInfo, SocialAccountPublic
from apps.api.services import oauth as oauth_service
from apps.api.services import social_accounts as accounts_service
from apps.api.services.platforms import (
    PlatformError,
    PlatformNotConfigured,
    UnknownPlatform,
    all_platforms,
    get_platform,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["accounts"])


def _resolve(platform: str):
    try:
        return get_platform(platform)
    except UnknownPlatform as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/platforms", response_model=list[PlatformInfo])
def list_platforms() -> list[PlatformInfo]:
    """Every supported platform and whether this deployment can use it."""
    return [
        PlatformInfo(
            name=client.name,
            label=client.label,
            configured=client.configuration_error() is None,
            requires_public_url=client.needs_public_url,
            scopes=list(client.scopes),
            detail=client.configuration_error(),
        )
        for client in all_platforms()
    ]


@router.get("/accounts", response_model=list[SocialAccountPublic])
def list_accounts(db: DbSession, user: CurrentUser) -> list[SocialAccountPublic]:
    """The caller's connected accounts. Token columns are never returned."""
    return [
        SocialAccountPublic.model_validate(account)
        for account in accounts_service.list_accounts(db, user.id)
    ]


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_account(account_id: int, db: DbSession, user: CurrentUser) -> Response:
    """Disconnect an account and erase its stored tokens."""
    account = accounts_service.get_account(db, user.id, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found."
        )
    accounts_service.disconnect(db, account)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/oauth/{platform}/authorize", response_model=AuthorizeUrl)
def authorize(platform: str, user: CurrentUser) -> AuthorizeUrl:
    """Begin a connection.

    Returns the provider URL rather than redirecting, because the caller is
    an authenticated XHR client: a 307 to a third-party login would be
    followed by fetch() and fail CORS instead of moving the browser.
    """
    client = _resolve(platform)
    try:
        url, _state = oauth_service.start_authorization(user.id, client.name)
    except PlatformNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except PlatformError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    return AuthorizeUrl(platform=client.name, authorize_url=url)


@router.get("/oauth/{platform}/callback")
async def callback(
    platform: str,
    db: DbSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    """Finish a connection.

    This endpoint is reached by the user's browser coming back from the
    provider, so it is deliberately *not* behind the bearer-token dependency
    — the redirect carries no Authorization header. The encrypted state blob
    is what authenticates the request and identifies the user.
    """
    client = _resolve(platform)

    if error:
        detail = error_description or error
        logger.info("%s authorisation was declined: %s", client.name, detail)
        return _finish(client.name, ok=False, message=detail)

    if not code:
        return _finish(
            client.name, ok=False, message="The provider returned no authorisation code."
        )

    try:
        account = await oauth_service.complete_authorization(
            db, client.name, code=code, state=state or ""
        )
    except oauth_service.OAuthStateError as exc:
        logger.warning("Rejected %s callback: %s", client.name, exc)
        return _finish(client.name, ok=False, message=str(exc))
    except PlatformError as exc:
        logger.warning("%s token exchange failed: %s", client.name, exc)
        return _finish(client.name, ok=False, message=str(exc))

    return _finish(client.name, ok=True, message=account.account_name)


def _finish(platform: str, *, ok: bool, message: str):
    """Send the browser back to the app with the outcome.

    Falls back to JSON when no app URL is configured, so the flow is still
    debuggable from a terminal.
    """
    base = (settings.APP_URL or "").rstrip("/")
    if not base:
        payload = {"platform": platform, "connected": ok, "detail": message}
        if ok:
            return payload
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=payload)

    query = urlencode(
        {
            "platform": platform,
            "status": "connected" if ok else "failed",
            "detail": message,
        }
    )
    return RedirectResponse(
        url=f"{base}/settings/accounts?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
