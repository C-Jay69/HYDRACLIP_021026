"""X (Twitter), via API v2 chunked media upload."""

from __future__ import annotations

import asyncio
import base64
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

API_ROOT = "https://api.x.com"

#: X rejects APPEND segments at or above 5MB, so stay comfortably under.
CHUNK_BYTES = 4 * 1024 * 1024


class XClient(PlatformClient):
    name = "x"
    label = "X"
    scopes = ("tweet.read", "tweet.write", "users.read", "offline.access")
    requires_pkce = True
    authorize_endpoint = "https://x.com/i/oauth2/authorize"
    token_endpoint = f"{API_ROOT}/2/oauth2/token"
    needs_public_url = False

    def authorize_url(self, state: str, code_challenge: str | None = None) -> str:
        self.require_configured()
        if not code_challenge:
            raise PlatformError("X requires PKCE; no code challenge was supplied.")
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            # offline.access is what makes X return a refresh token. Without
            # it the connection dies after two hours, permanently.
            "scope": " ".join(self.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.authorize_endpoint}?{urlencode(params)}"

    def _basic_auth(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}".encode()
        return base64.b64encode(raw).decode()

    async def exchange_code(self, code: str, code_verifier: str | None = None) -> TokenSet:
        self.require_configured()
        async with self._client() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "code_verifier": code_verifier or "",
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {self._basic_auth()}",
                },
            )
        self._raise_for_status(response, "X token exchange")
        payload = response.json()

        token = TokenSet(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at_from(payload.get("expires_in")),
            scope=payload.get("scope"),
            token_type=payload.get("token_type", "bearer"),
        )
        await self._attach_user(token)
        return token

    async def refresh(self, refresh_token: str) -> TokenSet:
        self.require_configured()
        async with self._client() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {self._basic_auth()}",
                },
            )
        self._raise_for_status(response, "X token refresh")
        payload = response.json()
        return TokenSet(
            access_token=payload["access_token"],
            # X rotates the refresh token on every use; keeping the old one
            # would break the next refresh.
            refresh_token=payload.get("refresh_token") or refresh_token,
            expires_at=expires_at_from(payload.get("expires_in")),
            scope=payload.get("scope"),
        )

    async def _attach_user(self, token: TokenSet) -> None:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"{API_ROOT}/2/users/me",
                    headers={"Authorization": f"Bearer {token.access_token}"},
                )
            if response.is_success:
                data = response.json().get("data", {})
                token.account_id = data.get("id")
                token.account_name = data.get("username")
        except Exception:  # noqa: BLE001 - cosmetic
            pass
        token.account_name = token.account_name or "X account"

    async def publish(self, token: str, request: PublishRequest) -> PublishResult:
        headers = {"Authorization": f"Bearer {token}"}
        media_id: str | None = None

        async with self._client(timeout=None) as client:
            if request.file_path and os.path.isfile(request.file_path):
                media_id = await self._upload_media(client, headers, request.file_path)

            body: dict = {"text": self._text(request)}
            if media_id:
                body["media"] = {"media_ids": [media_id]}

            response = await client.post(
                f"{API_ROOT}/2/tweets", headers=headers, json=body
            )
            self._raise_for_status(response, "X post creation")
            payload = response.json()

        data = payload.get("data") or {}
        post_id = data.get("id")
        if not post_id:
            raise PublishError(f"X returned no post id: {payload}")

        return PublishResult(
            post_id=post_id,
            url=f"https://x.com/i/web/status/{post_id}",
            raw=payload,
        )

    @staticmethod
    def _text(request: PublishRequest) -> str:
        """X caps posts at 280 characters, so the text has to be built to fit
        rather than assembled and sent hopefully."""
        text = request.title
        if request.description:
            candidate = f"{text}\n\n{request.description}"
            text = candidate if len(candidate) <= 280 else text
        if request.tags:
            tags = " ".join(f"#{t.lstrip('#')}" for t in request.tags[:5])
            candidate = f"{text}\n\n{tags}"
            if len(candidate) <= 280:
                text = candidate
        return text[:280]

    async def _upload_media(
        self, client: httpx.AsyncClient, headers: dict, path: str
    ) -> str:
        size = os.path.getsize(path)

        init = await client.post(
            f"{API_ROOT}/2/media/upload/initialize",
            headers=headers,
            json={
                "media_type": "video/mp4",
                "total_bytes": size,
                "media_category": "tweet_video",
            },
        )
        self._raise_for_status(init, "X media initialisation")
        media_id = (init.json().get("data") or {}).get("id")
        if not media_id:
            raise PublishError(f"X returned no media id: {init.text[:200]}")

        with open(path, "rb") as handle:
            index = 0
            while True:
                chunk = handle.read(CHUNK_BYTES)
                if not chunk:
                    break
                append = await client.post(
                    f"{API_ROOT}/2/media/upload/{media_id}/append",
                    headers=headers,
                    files={"media": ("chunk", chunk, "application/octet-stream")},
                    data={"segment_index": str(index)},
                )
                self._raise_for_status(append, f"X media upload (segment {index})")
                index += 1

        finalize = await client.post(
            f"{API_ROOT}/2/media/upload/{media_id}/finalize", headers=headers
        )
        self._raise_for_status(finalize, "X media finalisation")

        # Video always comes back with processing_info; the media id is not
        # usable in a post until that reaches succeeded.
        data = finalize.json().get("data") or {}
        if data.get("processing_info"):
            await self._await_processing(client, headers, media_id)

        return media_id

    async def _await_processing(
        self, client: httpx.AsyncClient, headers: dict, media_id: str
    ) -> None:
        deadline = asyncio.get_running_loop().time() + settings.PUBLISH_POLL_TIMEOUT_SECONDS

        while True:
            response = await client.get(
                f"{API_ROOT}/2/media/upload",
                headers=headers,
                params={"media_id": media_id, "command": "STATUS"},
            )
            self._raise_for_status(response, "X media status")
            info = (response.json().get("data") or {}).get("processing_info") or {}
            state = info.get("state")

            if state == "succeeded" or not state:
                return
            if state == "failed":
                error = info.get("error", {})
                raise PublishError(
                    f"X failed to process the video: "
                    f"{error.get('message', 'no reason given')}"
                )

            if asyncio.get_running_loop().time() >= deadline:
                raise PublishError(
                    f"X did not finish processing within "
                    f"{settings.PUBLISH_POLL_TIMEOUT_SECONDS:.0f}s "
                    f"(last state: {state})."
                )
            await asyncio.sleep(
                min(
                    float(info.get("check_after_secs") or settings.PUBLISH_POLL_INTERVAL_SECONDS),
                    settings.PUBLISH_POLL_INTERVAL_SECONDS * 4,
                )
            )
