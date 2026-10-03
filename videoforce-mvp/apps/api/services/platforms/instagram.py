"""Instagram Reels, via the Graph API container model."""

from __future__ import annotations

import asyncio
from urllib.parse import urlencode

import httpx

from apps.api.core.config import settings
from apps.api.services.platforms.base import (
    PlatformClient,
    PublishError,
    PublishRequest,
    PublishResult,
    TokenSet,
    expires_at_from,
)


class InstagramClient(PlatformClient):
    name = "instagram"
    label = "Instagram"
    scopes = (
        "instagram_business_basic",
        "instagram_business_content_publish",
    )
    authorize_endpoint = "https://www.instagram.com/oauth/authorize"
    token_endpoint = "https://api.instagram.com/oauth/access_token"
    #: Instagram never accepts bytes — it fetches the file from a URL you
    #: give it, which must be publicly reachable over HTTPS.
    needs_public_url = True
    can_upload_bytes = False

    @property
    def graph_root(self) -> str:
        return f"https://graph.instagram.com/{settings.INSTAGRAM_GRAPH_VERSION}"

    def authorize_url(self, state: str, code_challenge: str | None = None) -> str:
        self.require_configured()
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": ",".join(self.scopes),
            "state": state,
        }
        return f"{self.authorize_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str | None = None) -> TokenSet:
        self.require_configured()
        async with self._client() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
            )
        self._raise_for_status(response, "Instagram token exchange")
        payload = response.json()

        short_lived = payload["access_token"]
        account_id = str(payload.get("user_id") or "")

        # The code exchange yields a 1-hour token. Trading it for a 60-day
        # long-lived token immediately is the only way a scheduled post
        # tomorrow can still authenticate.
        token = await self._exchange_for_long_lived(short_lived)
        token.account_id = account_id or token.account_id
        token.scope = payload.get("permissions") or ",".join(self.scopes)
        await self._attach_profile(token)
        return token

    async def _exchange_for_long_lived(self, short_lived: str) -> TokenSet:
        async with self._client() as client:
            response = await client.get(
                f"{self.graph_root}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self.client_secret,
                    "access_token": short_lived,
                },
            )
        if not response.is_success:
            # Fall back to the short-lived token rather than failing the whole
            # connection; it will simply expire sooner.
            return TokenSet(access_token=short_lived, expires_at=expires_at_from(3600))

        payload = response.json()
        return TokenSet(
            access_token=payload.get("access_token", short_lived),
            expires_at=expires_at_from(payload.get("expires_in")),
            token_type=payload.get("token_type", "Bearer"),
        )

    async def refresh(self, refresh_token: str) -> TokenSet:
        """Instagram has no refresh token; a long-lived token refreshes itself.

        The caller passes the current access token here, which is why this
        provider stores the access token as its own refresh credential.
        """
        self.require_configured()
        async with self._client() as client:
            response = await client.get(
                f"{self.graph_root}/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": refresh_token,
                },
            )
        self._raise_for_status(response, "Instagram token refresh")
        payload = response.json()
        new_token = payload["access_token"]
        return TokenSet(
            access_token=new_token,
            refresh_token=new_token,
            expires_at=expires_at_from(payload.get("expires_in")),
        )

    async def _attach_profile(self, token: TokenSet) -> None:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"{self.graph_root}/me",
                    params={"fields": "id,username", "access_token": token.access_token},
                )
            if response.is_success:
                body = response.json()
                token.account_id = body.get("id") or token.account_id
                token.account_name = body.get("username")
        except Exception:  # noqa: BLE001 - cosmetic
            pass
        token.account_name = token.account_name or "Instagram account"

    async def publish(self, token: str, request: PublishRequest) -> PublishResult:
        if not request.video_url:
            raise PublishError(
                "Instagram downloads the video from a public HTTPS URL, and no "
                "such URL is available for this item. A public media host must "
                "be configured before Instagram publishing can work."
            )
        if not request.account_id:
            raise PublishError(
                "Instagram publishing needs the Instagram user id, which is "
                "missing from the connected account. Reconnect the account."
            )

        async with self._client(timeout=None) as client:
            # Step 1: create a media container describing the Reel.
            create = await client.post(
                f"{self.graph_root}/{request.account_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": request.video_url,
                    "caption": self._caption(request),
                    "share_to_feed": "true",
                    "access_token": token,
                },
            )
            self._raise_for_status(create, "Instagram container creation")
            container_id = create.json().get("id")
            if not container_id:
                raise PublishError(
                    f"Instagram returned no container id: {create.text[:200]}"
                )

            # Step 2: Instagram downloads and transcodes asynchronously. The
            # container is not publishable until it reports FINISHED, and
            # publishing early fails.
            await self._await_container(client, container_id, token)

            # Step 3: publish the finished container.
            publish = await client.post(
                f"{self.graph_root}/{request.account_id}/media_publish",
                data={"creation_id": container_id, "access_token": token},
            )
            self._raise_for_status(publish, "Instagram publish")
            body = publish.json()

        media_id = body.get("id")
        if not media_id:
            raise PublishError(f"Instagram returned no media id: {body}")

        return PublishResult(post_id=media_id, url=None, raw=body)

    @staticmethod
    def _caption(request: PublishRequest) -> str:
        parts = [request.title]
        if request.description:
            parts.append(request.description)
        if request.tags:
            parts.append(" ".join(f"#{t.lstrip('#')}" for t in request.tags[:30]))
        return "\n\n".join(p for p in parts if p)[:2200]

    async def _await_container(
        self, client: httpx.AsyncClient, container_id: str, token: str
    ) -> None:
        deadline = asyncio.get_running_loop().time() + settings.PUBLISH_POLL_TIMEOUT_SECONDS

        while True:
            response = await client.get(
                f"{self.graph_root}/{container_id}",
                params={"fields": "status_code,status", "access_token": token},
            )
            self._raise_for_status(response, "Instagram container status")
            body = response.json()
            status = body.get("status_code")

            if status == "FINISHED":
                return
            if status in {"ERROR", "EXPIRED"}:
                raise PublishError(
                    f"Instagram failed to process the video ({status}): "
                    f"{body.get('status', 'no detail given')}"
                )

            if asyncio.get_running_loop().time() >= deadline:
                raise PublishError(
                    f"Instagram did not finish processing within "
                    f"{settings.PUBLISH_POLL_TIMEOUT_SECONDS:.0f}s "
                    f"(last status: {status})."
                )
            await asyncio.sleep(settings.PUBLISH_POLL_INTERVAL_SECONDS)
