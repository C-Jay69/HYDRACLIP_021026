"""TikTok, via the Content Posting API."""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlencode

import httpx

from apps.api.core.config import settings
from apps.api.services.platforms.base import (
    PlatformClient,
    PlatformError,
    PublishError,
    PublishRequest,
    PublishResult,
    TokenSet,
    expires_at_from,
)

API_ROOT = "https://open.tiktokapis.com"

#: Only these mean the post is live or definitively dead. Everything else is
#: still in flight.
TERMINAL_OK = "PUBLISH_COMPLETE"
TERMINAL_FAIL = {"FAILED"}


class TikTokClient(PlatformClient):
    name = "tiktok"
    label = "TikTok"
    scopes = ("user.info.basic", "video.publish")
    requires_pkce = True
    authorize_endpoint = "https://www.tiktok.com/v2/auth/authorize/"
    token_endpoint = f"{API_ROOT}/v2/oauth/token/"
    needs_public_url = True

    def authorize_url(self, state: str, code_challenge: str | None = None) -> str:
        self.require_configured()
        if not code_challenge:
            raise PlatformError("TikTok requires PKCE; no code challenge was supplied.")
        params = {
            # TikTok calls it client_key, not client_id.
            "client_key": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": ",".join(self.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.authorize_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str | None = None) -> TokenSet:
        self.require_configured()
        async with self._client() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "client_key": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code_verifier": code_verifier or "",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        self._raise_for_status(response, "TikTok token exchange")
        payload = response.json()
        self._raise_payload_error(payload, "TikTok token exchange")

        token = TokenSet(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at_from(payload.get("expires_in")),
            scope=payload.get("scope"),
            account_id=payload.get("open_id"),
        )
        await self._attach_creator(token)
        return token

    async def refresh(self, refresh_token: str) -> TokenSet:
        self.require_configured()
        async with self._client() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "client_key": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        self._raise_for_status(response, "TikTok token refresh")
        payload = response.json()
        self._raise_payload_error(payload, "TikTok token refresh")
        return TokenSet(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token") or refresh_token,
            expires_at=expires_at_from(payload.get("expires_in")),
            scope=payload.get("scope"),
            account_id=payload.get("open_id"),
        )

    async def _attach_creator(self, token: TokenSet) -> None:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"{API_ROOT}/v2/user/info/",
                    params={"fields": "open_id,display_name"},
                    headers={"Authorization": f"Bearer {token.access_token}"},
                )
            if response.is_success:
                user = response.json().get("data", {}).get("user", {})
                token.account_id = user.get("open_id") or token.account_id
                token.account_name = user.get("display_name")
        except Exception:  # noqa: BLE001 - cosmetic
            pass
        token.account_name = token.account_name or "TikTok account"

    @staticmethod
    def _raise_payload_error(payload: dict, action: str) -> None:
        """TikTok returns HTTP 200 with an error object inside, so the status
        code alone is not enough to know whether the call worked."""
        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            if code and code != "ok":
                raise PlatformError(
                    f"{action} failed: {code} - {error.get('message', '')}"
                )
        elif isinstance(error, str) and error:
            raise PlatformError(
                f"{action} failed: {error} - {payload.get('error_description', '')}"
            )

    async def publish(self, token: str, request: PublishRequest) -> PublishResult:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        async with self._client(timeout=None) as client:
            # TikTok requires querying creator_info before every post; it
            # returns which privacy levels this creator is actually allowed
            # to use, which varies by account and by app audit status.
            info = await client.post(
                f"{API_ROOT}/v2/post/publish/creator_info/query/", headers=headers
            )
            self._raise_for_status(info, "TikTok creator info query")
            info_payload = info.json()
            self._raise_payload_error(info_payload, "TikTok creator info query")

            allowed = info_payload.get("data", {}).get("privacy_level_options") or []
            privacy = self._privacy_level(request.privacy, allowed)

            init_body = {
                "post_info": {
                    "title": request.title[:2200],
                    "privacy_level": privacy,
                    "disable_comment": False,
                    "disable_duet": False,
                    "disable_stitch": False,
                },
                "source_info": self._source_info(request),
            }

            init = await client.post(
                f"{API_ROOT}/v2/post/publish/video/init/",
                headers=headers,
                json=init_body,
            )
            self._raise_for_status(init, "TikTok publish initiation")
            init_payload = init.json()
            self._raise_payload_error(init_payload, "TikTok publish initiation")

            data = init_payload.get("data") or {}
            publish_id = data.get("publish_id")
            if not publish_id:
                raise PublishError(f"TikTok returned no publish_id: {init_payload}")

            # FILE_UPLOAD hands back a URL to PUT the bytes to.
            upload_url = data.get("upload_url")
            if upload_url and request.file_path:
                await self._upload_file(client, upload_url, request.file_path)

            status = await self._await_completion(client, headers, publish_id)

        return PublishResult(
            post_id=publish_id,
            url=None,  # TikTok does not return a permalink from this API.
            raw=status,
        )

    def _source_info(self, request: PublishRequest) -> dict:
        """PULL_FROM_URL when we have a public URL, FILE_UPLOAD otherwise.

        PULL_FROM_URL only works for domains verified in the TikTok developer
        portal, so it fails for arbitrary URLs.
        """
        if request.video_url:
            return {"source": "PULL_FROM_URL", "video_url": request.video_url}

        if not request.file_path or not os.path.isfile(request.file_path):
            raise PublishError(
                "TikTok needs either a publicly reachable video URL or a local "
                "video file, and neither is available for this item."
            )

        size = os.path.getsize(request.file_path)
        return {
            "source": "FILE_UPLOAD",
            "video_size": size,
            # One chunk; TikTok allows up to 64MB per chunk.
            "chunk_size": size,
            "total_chunk_count": 1,
        }

    @staticmethod
    def _privacy_level(requested: str, allowed: list[str]) -> str:
        """Map our generic privacy word onto a level this creator may use.

        Unaudited apps are restricted to SELF_ONLY, so asking for a public
        post would be rejected outright.
        """
        preference = {
            "public": ["PUBLIC_TO_EVERYONE", "FOLLOWER_OF_CREATOR", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
            "unlisted": ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR"],
            "private": ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS"],
        }.get(requested, ["SELF_ONLY"])

        for level in preference:
            if level in allowed:
                return level
        if allowed:
            return allowed[0]
        return "SELF_ONLY"

    async def _upload_file(
        self, client: httpx.AsyncClient, upload_url: str, path: str
    ) -> None:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            response = await client.put(
                upload_url,
                content=handle.read(),
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(size),
                    "Content-Range": f"bytes 0-{size - 1}/{size}",
                },
            )
        self._raise_for_status(response, "TikTok file upload")

    async def _await_completion(
        self, client: httpx.AsyncClient, headers: dict, publish_id: str
    ) -> dict:
        """Poll until TikTok says the post is live.

        An init call that succeeds means nothing on its own — TikTok processes
        asynchronously and only PUBLISH_COMPLETE means the video actually
        posted.
        """
        deadline = asyncio.get_running_loop().time() + settings.PUBLISH_POLL_TIMEOUT_SECONDS
        last: dict = {}

        while True:
            response = await client.post(
                f"{API_ROOT}/v2/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id},
            )
            self._raise_for_status(response, "TikTok publish status")
            last = response.json()
            self._raise_payload_error(last, "TikTok publish status")

            status = (last.get("data") or {}).get("status")
            if status == TERMINAL_OK:
                return last
            if status in TERMINAL_FAIL:
                reason = (last.get("data") or {}).get("fail_reason", "no reason given")
                raise PublishError(f"TikTok rejected the video: {reason}")

            if asyncio.get_running_loop().time() >= deadline:
                raise PublishError(
                    f"TikTok did not finish processing within "
                    f"{settings.PUBLISH_POLL_TIMEOUT_SECONDS:.0f}s "
                    f"(last status: {status})."
                )
            await asyncio.sleep(settings.PUBLISH_POLL_INTERVAL_SECONDS)
