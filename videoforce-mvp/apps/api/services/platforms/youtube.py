"""YouTube, via the Data API v3 resumable upload."""

from __future__ import annotations

import os
from urllib.parse import urlencode

from apps.api.services.platforms.base import (
    PlatformClient,
    PublishError,
    PublishRequest,
    PublishResult,
    TokenSet,
    expires_at_from,
)

UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubeClient(PlatformClient):
    name = "youtube"
    label = "YouTube"
    scopes = ("https://www.googleapis.com/auth/youtube.upload",)
    authorize_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint = "https://oauth2.googleapis.com/token"
    needs_public_url = False

    def authorize_url(self, state: str, code_challenge: str | None = None) -> str:
        self.require_configured()
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            # Google only returns a refresh token when both of these are set,
            # and only on the first consent unless prompt=consent forces it.
            # Without them a connection silently dies after an hour.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"{self.authorize_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str | None = None) -> TokenSet:
        self.require_configured()
        async with self._client() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        self._raise_for_status(response, "YouTube token exchange")
        payload = response.json()

        token = TokenSet(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at_from(payload.get("expires_in")),
            scope=payload.get("scope"),
            token_type=payload.get("token_type", "Bearer"),
        )
        await self._attach_channel(token)
        return token

    async def refresh(self, refresh_token: str) -> TokenSet:
        self.require_configured()
        async with self._client() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                },
            )
        self._raise_for_status(response, "YouTube token refresh")
        payload = response.json()
        return TokenSet(
            access_token=payload["access_token"],
            # Google does not reissue the refresh token; keep the existing one.
            refresh_token=payload.get("refresh_token") or refresh_token,
            expires_at=expires_at_from(payload.get("expires_in")),
            scope=payload.get("scope"),
        )

    async def _attach_channel(self, token: TokenSet) -> None:
        """Best-effort channel identity, so the UI can name the connection."""
        try:
            async with self._client() as client:
                response = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "snippet", "mine": "true"},
                    headers={"Authorization": f"Bearer {token.access_token}"},
                )
            if response.is_success:
                items = response.json().get("items") or []
                if items:
                    token.account_id = items[0].get("id")
                    token.account_name = items[0].get("snippet", {}).get("title")
        except Exception:  # noqa: BLE001 - identity is cosmetic, never fatal
            pass

        token.account_name = token.account_name or "YouTube channel"

    async def publish(self, token: str, request: PublishRequest) -> PublishResult:
        if not request.file_path or not os.path.isfile(request.file_path):
            raise PublishError(
                "YouTube uploads the file itself, but no rendered video file "
                "is available for this item."
            )

        size = os.path.getsize(request.file_path)
        metadata = {
            "snippet": {
                "title": request.title[:100],
                "description": request.description[:5000],
                "tags": request.tags[:30],
            },
            "status": {
                "privacyStatus": request.privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        async with self._client(timeout=None) as client:
            # Step 1: open a resumable session. The session URL comes back in
            # the Location header, not the body.
            init = await client.post(
                UPLOAD_URL,
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Length": str(size),
                    "X-Upload-Content-Type": "video/mp4",
                },
                json=metadata,
            )
            self._raise_for_status(init, "YouTube upload initiation")

            session_url = init.headers.get("location")
            if not session_url:
                raise PublishError(
                    "YouTube accepted the upload request but returned no "
                    "resumable session URL."
                )

            # Step 2: send the bytes in one PUT. Chunked resume would be an
            # improvement for very large files.
            with open(request.file_path, "rb") as handle:
                upload = await client.put(
                    session_url,
                    content=handle.read(),
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "video/mp4",
                        "Content-Length": str(size),
                    },
                )
            self._raise_for_status(upload, "YouTube upload")

        body = upload.json()
        video_id = body.get("id")
        if not video_id:
            raise PublishError(f"YouTube returned no video id: {body}")

        return PublishResult(
            post_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            raw=body,
        )
