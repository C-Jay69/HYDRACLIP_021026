"""Platform clients, exercised against mocked provider responses.

Real developer credentials for YouTube, Instagram, TikTok and X are not
available here, so every provider interaction is verified against an
``httpx.MockTransport`` that replays the documented request/response shapes.
This proves the client sends what the API expects and interprets what it
sends back; it does not prove the live services behave as documented.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from apps.api.core.config import settings
from apps.api.services.platforms import (
    InstagramClient,
    PlatformAuthError,
    PlatformError,
    PlatformNotConfigured,
    PublishError,
    PublishRequest,
    TikTokClient,
    UnknownPlatform,
    XClient,
    YouTubeClient,
    all_platforms,
    generate_pkce_pair,
    get_platform,
)


@pytest.fixture
def configured(monkeypatch):
    """Give every platform credentials so configuration checks pass."""
    for name in ("YOUTUBE", "INSTAGRAM", "TIKTOK", "X"):
        monkeypatch.setattr(settings, f"{name}_CLIENT_ID", f"{name.lower()}-id")
        monkeypatch.setattr(settings, f"{name}_CLIENT_SECRET", f"{name.lower()}-secret")
        monkeypatch.setattr(
            settings,
            f"{name}_REDIRECT_URI",
            f"https://app.example.com/oauth/{name.lower()}/callback",
        )


def mount(client, handler):
    """Route the client's HTTP calls to a mock transport."""
    transport = httpx.MockTransport(handler)

    def _factory(**kwargs):
        kwargs.pop("timeout", None)
        return httpx.AsyncClient(transport=transport, timeout=5.0, **kwargs)

    client._client = _factory  # type: ignore[method-assign]
    return client


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def instant_polling(monkeypatch):
    """Make poll loops spin without real delay.

    Patching asyncio.sleep via the provider module does not work: the module
    attribute *is* the asyncio module, so assigning to it patches sleep
    globally and the replacement recurses into itself.
    """
    monkeypatch.setattr(settings, "PUBLISH_POLL_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(settings, "PUBLISH_POLL_TIMEOUT_SECONDS", 5.0)


@pytest.fixture
def video_file(tmp_path):
    path = tmp_path / "render.mp4"
    path.write_bytes(b"\x00" * 2048)
    return str(path)


# --- Registry and configuration ------------------------------------------------


class TestRegistry:
    def test_all_four_platforms_are_registered(self):
        assert {c.name for c in all_platforms()} == {
            "youtube",
            "instagram",
            "tiktok",
            "x",
        }

    def test_lookup_is_case_insensitive(self):
        assert get_platform("YouTube").name == "youtube"

    def test_unknown_platform_lists_the_supported_ones(self):
        with pytest.raises(UnknownPlatform, match="youtube, instagram, tiktok, x"):
            get_platform("facebook")

    def test_unconfigured_platform_names_the_missing_settings(self):
        error = YouTubeClient().configuration_error()
        assert "YOUTUBE_CLIENT_ID" in error
        assert "YOUTUBE_CLIENT_SECRET" in error

    def test_configured_platform_reports_no_problem(self, configured):
        assert YouTubeClient().configuration_error() is None

    def test_authorize_refuses_without_configuration(self):
        with pytest.raises(PlatformNotConfigured):
            YouTubeClient().authorize_url(state="s")


class TestPkce:
    def test_challenge_is_the_s256_of_the_verifier(self):
        verifier, challenge = generate_pkce_pair()
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert challenge == expected

    def test_verifier_length_is_within_the_spec(self):
        verifier, _ = generate_pkce_pair()
        assert 43 <= len(verifier) <= 128

    def test_challenge_is_unpadded(self):
        _, challenge = generate_pkce_pair()
        assert "=" not in challenge

    def test_pairs_are_unique(self):
        assert generate_pkce_pair()[0] != generate_pkce_pair()[0]


# --- YouTube -----------------------------------------------------------------------


class TestYouTubeAuth:
    def test_authorize_url_requests_offline_access(self, configured):
        """Without access_type=offline Google returns no refresh token and
        the connection silently dies after an hour."""
        url = YouTubeClient().authorize_url(state="xyz")
        params = parse_qs(urlparse(url).query)
        assert params["access_type"] == ["offline"]
        assert params["prompt"] == ["consent"]
        assert params["state"] == ["xyz"]
        assert params["response_type"] == ["code"]
        assert "youtube.upload" in params["scope"][0]

    def test_exchange_sends_the_client_secret_and_reads_the_channel(self, configured):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if "oauth2.googleapis.com" in str(request.url):
                seen["token"] = dict(parse_qs(request.content.decode()))
                return httpx.Response(
                    200,
                    json={
                        "access_token": "at",
                        "refresh_token": "rt",
                        "expires_in": 3600,
                        "scope": "https://www.googleapis.com/auth/youtube.upload",
                    },
                )
            return httpx.Response(
                200,
                json={"items": [{"id": "UC123", "snippet": {"title": "My Channel"}}]},
            )

        token = run(mount(YouTubeClient(), handler).exchange_code("the-code"))

        assert seen["token"]["grant_type"] == ["authorization_code"]
        assert seen["token"]["client_secret"] == ["youtube-secret"]
        assert token.access_token == "at"
        assert token.refresh_token == "rt"
        assert token.expires_at is not None
        assert token.account_id == "UC123"
        assert token.account_name == "My Channel"

    def test_channel_lookup_failure_does_not_break_the_connection(self, configured):
        def handler(request: httpx.Request) -> httpx.Response:
            if "oauth2.googleapis.com" in str(request.url):
                return httpx.Response(200, json={"access_token": "at", "expires_in": 60})
            return httpx.Response(500, text="boom")

        token = run(mount(YouTubeClient(), handler).exchange_code("c"))
        assert token.access_token == "at"
        assert token.account_name == "YouTube channel"

    def test_refresh_keeps_the_existing_refresh_token(self, configured):
        """Google does not reissue the refresh token, so dropping it would
        break the next refresh."""

        def handler(request):
            return httpx.Response(200, json={"access_token": "new", "expires_in": 3600})

        token = run(mount(YouTubeClient(), handler).refresh("original-rt"))
        assert token.access_token == "new"
        assert token.refresh_token == "original-rt"

    def test_rejected_exchange_raises_auth_error(self, configured):
        def handler(request):
            return httpx.Response(
                401, json={"error": "invalid_grant", "error_description": "Bad code"}
            )

        with pytest.raises(PlatformAuthError, match="Bad code"):
            run(mount(YouTubeClient(), handler).exchange_code("c"))


class TestYouTubePublish:
    def test_resumable_upload_follows_the_location_header(self, configured, video_file):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, str(request.url)))
            if request.method == "POST":
                assert request.headers["x-upload-content-length"] == "2048"
                body = request.read().decode()
                assert "My title" in body
                return httpx.Response(
                    200, headers={"location": "https://upload.example/session/42"}
                )
            return httpx.Response(200, json={"id": "vid123"})

        result = run(
            mount(YouTubeClient(), handler).publish(
                "at",
                PublishRequest(
                    video_url=None,
                    file_path=video_file,
                    title="My title",
                    description="d",
                    privacy="private",
                ),
            )
        )

        assert result.post_id == "vid123"
        assert result.url == "https://www.youtube.com/watch?v=vid123"
        assert calls[1] == ("PUT", "https://upload.example/session/42")

    def test_missing_session_url_is_an_error(self, configured, video_file):
        def handler(request):
            return httpx.Response(200)  # no Location header

        with pytest.raises(PublishError, match="no resumable session URL"):
            run(
                mount(YouTubeClient(), handler).publish(
                    "at",
                    PublishRequest(None, video_file, "t"),
                )
            )

    def test_title_is_truncated_to_the_api_limit(self, configured, video_file):
        captured = {}

        def handler(request):
            if request.method == "POST":
                captured["body"] = request.read().decode()
                return httpx.Response(200, headers={"location": "https://u/1"})
            return httpx.Response(200, json={"id": "v"})

        run(
            mount(YouTubeClient(), handler).publish(
                "at", PublishRequest(None, video_file, "x" * 300)
            )
        )
        import json as _json

        assert len(_json.loads(captured["body"])["snippet"]["title"]) == 100

    def test_absent_file_fails_before_any_request(self, configured):
        def handler(request):  # pragma: no cover - must never be called
            raise AssertionError("no HTTP call should be made")

        with pytest.raises(PublishError, match="no rendered video file"):
            run(
                mount(YouTubeClient(), handler).publish(
                    "at", PublishRequest(None, "/does/not/exist.mp4", "t")
                )
            )


# --- Instagram ------------------------------------------------------------------------


class TestInstagram:
    def test_exchange_upgrades_to_a_long_lived_token(self, configured):
        """A 1-hour token is useless for a post scheduled tomorrow."""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "oauth/access_token" in url:
                return httpx.Response(200, json={"access_token": "short", "user_id": 99})
            if "access_token" in url and "ig_exchange_token" in url:
                return httpx.Response(
                    200, json={"access_token": "long-lived", "expires_in": 5184000}
                )
            return httpx.Response(200, json={"id": "99", "username": "creator"})

        token = run(mount(InstagramClient(), handler).exchange_code("code"))
        assert token.access_token == "long-lived"
        assert token.account_id == "99"
        assert token.account_name == "creator"

    def test_falls_back_to_the_short_token_if_the_upgrade_fails(self, configured):
        def handler(request):
            url = str(request.url)
            if "oauth/access_token" in url:
                return httpx.Response(200, json={"access_token": "short", "user_id": 1})
            if "ig_exchange_token" in url:
                return httpx.Response(400, json={"error": {"message": "nope"}})
            return httpx.Response(200, json={"id": "1", "username": "c"})

        token = run(mount(InstagramClient(), handler).exchange_code("code"))
        assert token.access_token == "short"

    def test_refresh_uses_the_access_token_as_its_own_credential(self, configured):
        def handler(request):
            assert "ig_refresh_token" in str(request.url)
            return httpx.Response(
                200, json={"access_token": "renewed", "expires_in": 5184000}
            )

        token = run(mount(InstagramClient(), handler).refresh("current-access"))
        assert token.access_token == "renewed"
        assert token.refresh_token == "renewed"

    def test_publish_waits_for_the_container_to_finish(self, configured, instant_polling):
        """Publishing before status_code is FINISHED fails at the provider."""
        statuses = iter(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            calls.append(url)
            if request.method == "POST" and url.endswith("/media"):
                body = parse_qs(request.content.decode())
                assert body["media_type"] == ["REELS"]
                assert body["video_url"] == ["https://cdn.example/v.mp4"]
                return httpx.Response(200, json={"id": "container-1"})
            if request.method == "GET":
                return httpx.Response(200, json={"status_code": next(statuses)})
            return httpx.Response(200, json={"id": "media-9"})

        result = run(
            mount(InstagramClient(), handler).publish(
                "tok",
                PublishRequest(
                    video_url="https://cdn.example/v.mp4",
                    file_path=None,
                    title="Reel",
                    description="desc",
                    tags=["a", "b"],
                    account_id="99",
                ),
            )
        )

        assert result.post_id == "media-9"
        assert sum(1 for c in calls if "container-1" in c) == 3

    def test_container_error_is_terminal(self, configured):
        def handler(request):
            url = str(request.url)
            if request.method == "POST" and url.endswith("/media"):
                return httpx.Response(200, json={"id": "c1"})
            return httpx.Response(200, json={"status_code": "ERROR", "status": "bad codec"})

        with pytest.raises(PublishError, match="bad codec"):
            run(
                mount(InstagramClient(), handler).publish(
                    "t",
                    PublishRequest("https://cdn/v.mp4", None, "t", account_id="1"),
                )
            )

    def test_publish_without_a_public_url_is_refused(self, configured):
        def handler(request):  # pragma: no cover
            raise AssertionError("no HTTP call should be made")

        with pytest.raises(PublishError, match="public HTTPS URL"):
            run(
                mount(InstagramClient(), handler).publish(
                    "t", PublishRequest(None, "/tmp/x.mp4", "t", account_id="1")
                )
            )

    def test_publish_without_an_account_id_is_refused(self, configured):
        def handler(request):  # pragma: no cover
            raise AssertionError("no HTTP call should be made")

        with pytest.raises(PublishError, match="Instagram user id"):
            run(
                mount(InstagramClient(), handler).publish(
                    "t", PublishRequest("https://cdn/v.mp4", None, "t")
                )
            )

    def test_caption_combines_title_description_and_tags(self, configured):
        client = InstagramClient()
        caption = client._caption(
            PublishRequest(None, None, "Title", "Body", tags=["one", "#two"])
        )
        assert caption.startswith("Title")
        assert "Body" in caption
        assert "#one #two" in caption


# --- TikTok ---------------------------------------------------------------------------


class TestTikTok:
    def test_authorize_url_uses_client_key_and_pkce(self, configured):
        _, challenge = generate_pkce_pair()
        url = TikTokClient().authorize_url(state="s", code_challenge=challenge)
        params = parse_qs(urlparse(url).query)
        # TikTok names the parameter client_key, not client_id.
        assert params["client_key"] == ["tiktok-id"]
        assert params["code_challenge_method"] == ["S256"]
        assert "video.publish" in params["scope"][0]

    def test_authorize_without_pkce_is_refused(self, configured):
        with pytest.raises(PlatformError, match="PKCE"):
            TikTokClient().authorize_url(state="s")

    def test_exchange_sends_the_code_verifier(self, configured):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if "oauth/token" in str(request.url):
                seen.update(parse_qs(request.content.decode()))
                return httpx.Response(
                    200,
                    json={
                        "access_token": "at",
                        "refresh_token": "rt",
                        "expires_in": 86400,
                        "open_id": "open-1",
                        "scope": "video.publish",
                    },
                )
            return httpx.Response(
                200, json={"data": {"user": {"open_id": "open-1", "display_name": "Cre"}}}
            )

        token = run(mount(TikTokClient(), handler).exchange_code("c", code_verifier="ver"))
        assert seen["code_verifier"] == ["ver"]
        assert token.account_id == "open-1"
        assert token.account_name == "Cre"

    def test_error_inside_a_200_response_is_detected(self, configured):
        """TikTok returns HTTP 200 with an error object, so the status code
        alone cannot be trusted."""

        def handler(request):
            return httpx.Response(
                200,
                json={"error": {"code": "invalid_grant", "message": "expired code"}},
            )

        with pytest.raises(PlatformError, match="expired code"):
            run(mount(TikTokClient(), handler).exchange_code("c", code_verifier="v"))

    def test_publish_queries_creator_info_then_polls_to_completion(
        self, configured, instant_polling
    ):
        statuses = iter(["PROCESSING_UPLOAD", "PUBLISH_COMPLETE"])
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "creator_info/query" in url:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "privacy_level_options": [
                                "PUBLIC_TO_EVERYONE",
                                "SELF_ONLY",
                            ]
                        }
                    },
                )
            if "video/init" in url:
                seen["init"] = request.read().decode()
                return httpx.Response(200, json={"data": {"publish_id": "pub-7"}})
            return httpx.Response(200, json={"data": {"status": next(statuses)}})

        result = run(
            mount(TikTokClient(), handler).publish(
                "at",
                PublishRequest(
                    video_url="https://cdn.example/v.mp4",
                    file_path=None,
                    title="Clip",
                    privacy="public",
                ),
            )
        )

        assert result.post_id == "pub-7"
        assert "PULL_FROM_URL" in seen["init"]
        assert "PUBLIC_TO_EVERYONE" in seen["init"]

    def test_privacy_falls_back_to_what_the_creator_may_use(self, configured):
        """An unaudited app can only post SELF_ONLY; asking for public would
        be rejected outright."""
        client = TikTokClient()
        assert client._privacy_level("public", ["SELF_ONLY"]) == "SELF_ONLY"
        assert (
            client._privacy_level("public", ["PUBLIC_TO_EVERYONE", "SELF_ONLY"])
            == "PUBLIC_TO_EVERYONE"
        )
        assert client._privacy_level("private", ["SELF_ONLY"]) == "SELF_ONLY"
        assert client._privacy_level("public", []) == "SELF_ONLY"

    def test_failed_status_is_terminal(self, configured):
        def handler(request):
            url = str(request.url)
            if "creator_info" in url:
                return httpx.Response(200, json={"data": {"privacy_level_options": ["SELF_ONLY"]}})
            if "video/init" in url:
                return httpx.Response(200, json={"data": {"publish_id": "p"}})
            return httpx.Response(
                200, json={"data": {"status": "FAILED", "fail_reason": "spam_risk"}}
            )

        with pytest.raises(PublishError, match="spam_risk"):
            run(
                mount(TikTokClient(), handler).publish(
                    "at", PublishRequest("https://cdn/v.mp4", None, "t")
                )
            )

    def test_file_upload_path_sends_the_bytes(self, configured, video_file):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "creator_info" in url:
                return httpx.Response(200, json={"data": {"privacy_level_options": ["SELF_ONLY"]}})
            if "video/init" in url:
                seen["init"] = request.read().decode()
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "publish_id": "p1",
                            "upload_url": "https://upload.tiktok/1",
                        }
                    },
                )
            if request.method == "PUT":
                seen["range"] = request.headers.get("content-range")
                return httpx.Response(200)
            return httpx.Response(200, json={"data": {"status": "PUBLISH_COMPLETE"}})

        run(
            mount(TikTokClient(), handler).publish(
                "at", PublishRequest(None, video_file, "t")
            )
        )
        assert "FILE_UPLOAD" in seen["init"]
        assert seen["range"] == "bytes 0-2047/2048"

    def test_no_media_at_all_is_refused(self, configured):
        def handler(request):
            url = str(request.url)
            if "creator_info" in url:
                return httpx.Response(200, json={"data": {"privacy_level_options": ["SELF_ONLY"]}})
            raise AssertionError("init should not be reached")

        with pytest.raises(PublishError, match="publicly reachable video URL"):
            run(mount(TikTokClient(), handler).publish("at", PublishRequest(None, None, "t")))


# --- X ------------------------------------------------------------------------------------


class TestX:
    def test_authorize_url_requests_offline_access(self, configured):
        """offline.access is what makes X return a refresh token; its tokens
        expire every two hours."""
        _, challenge = generate_pkce_pair()
        url = XClient().authorize_url(state="s", code_challenge=challenge)
        params = parse_qs(urlparse(url).query)
        assert "offline.access" in params["scope"][0]
        assert "tweet.write" in params["scope"][0]
        assert params["code_challenge_method"] == ["S256"]

    def test_exchange_uses_basic_auth(self, configured):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if "oauth2/token" in str(request.url):
                seen["auth"] = request.headers.get("authorization", "")
                return httpx.Response(
                    200,
                    json={
                        "access_token": "at",
                        "refresh_token": "rt",
                        "expires_in": 7200,
                        "scope": "tweet.write offline.access",
                    },
                )
            return httpx.Response(200, json={"data": {"id": "1", "username": "user"}})

        token = run(mount(XClient(), handler).exchange_code("c", code_verifier="v"))
        assert seen["auth"].startswith("Basic ")
        decoded = base64.b64decode(seen["auth"].split()[1]).decode()
        assert decoded == "x-id:x-secret"
        assert token.account_name == "user"

    def test_refresh_adopts_the_rotated_refresh_token(self, configured):
        """X issues a new refresh token on every use; keeping the old one
        breaks the next refresh."""

        def handler(request):
            return httpx.Response(
                200,
                json={"access_token": "a2", "refresh_token": "r2", "expires_in": 7200},
            )

        token = run(mount(XClient(), handler).refresh("r1"))
        assert token.refresh_token == "r2"

    def test_publish_uploads_media_then_posts(self, configured, video_file):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            calls.append(url.rsplit("/", 1)[-1].split("?")[0])
            if url.endswith("/initialize"):
                return httpx.Response(200, json={"data": {"id": "media-1"}})
            if url.endswith("/append"):
                return httpx.Response(200)
            if url.endswith("/finalize"):
                return httpx.Response(200, json={"data": {"id": "media-1"}})
            if url.endswith("/tweets"):
                body = request.read().decode()
                assert "media-1" in body
                return httpx.Response(201, json={"data": {"id": "post-5"}})
            return httpx.Response(200, json={})

        result = run(
            mount(XClient(), handler).publish(
                "at", PublishRequest(None, video_file, "Hello")
            )
        )
        assert result.post_id == "post-5"
        assert result.url == "https://x.com/i/web/status/post-5"
        assert calls == ["initialize", "append", "finalize", "tweets"]

    def test_video_processing_is_awaited(self, configured, video_file, instant_polling):
        states = iter(["in_progress", "succeeded"])

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.endswith("/initialize"):
                return httpx.Response(200, json={"data": {"id": "m"}})
            if url.endswith("/append"):
                return httpx.Response(200)
            if url.endswith("/finalize"):
                return httpx.Response(
                    200,
                    json={"data": {"id": "m", "processing_info": {"state": "pending"}}},
                )
            if request.method == "GET":
                return httpx.Response(
                    200, json={"data": {"processing_info": {"state": next(states)}}}
                )
            return httpx.Response(201, json={"data": {"id": "p"}})

        result = run(
            mount(XClient(), handler).publish("at", PublishRequest(None, video_file, "t"))
        )
        assert result.post_id == "p"

    def test_failed_processing_raises(self, configured, video_file, instant_polling):
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.endswith("/initialize"):
                return httpx.Response(200, json={"data": {"id": "m"}})
            if url.endswith("/append"):
                return httpx.Response(200)
            if url.endswith("/finalize"):
                return httpx.Response(
                    200, json={"data": {"processing_info": {"state": "pending"}}}
                )
            return httpx.Response(
                200,
                json={
                    "data": {
                        "processing_info": {
                            "state": "failed",
                            "error": {"message": "UnsupportedMedia"},
                        }
                    }
                },
            )

        with pytest.raises(PublishError, match="UnsupportedMedia"):
            run(mount(XClient(), handler).publish("at", PublishRequest(None, video_file, "t")))

    def test_text_is_capped_at_280_characters(self):
        text = XClient()._text(
            PublishRequest(None, None, "t" * 100, "d" * 400, tags=["tag"])
        )
        assert len(text) <= 280
        # The description did not fit, so it was dropped rather than truncated
        # mid-sentence.
        assert text.startswith("t" * 100)

    def test_text_includes_tags_when_they_fit(self):
        text = XClient()._text(PublishRequest(None, None, "Short", "Body", tags=["x"]))
        assert "#x" in text and "Body" in text

    def test_post_without_media_still_works(self, configured):
        def handler(request):
            assert str(request.url).endswith("/tweets")
            assert "media" not in request.read().decode()
            return httpx.Response(201, json={"data": {"id": "p9"}})

        result = run(mount(XClient(), handler).publish("at", PublishRequest(None, None, "Text only")))
        assert result.post_id == "p9"
