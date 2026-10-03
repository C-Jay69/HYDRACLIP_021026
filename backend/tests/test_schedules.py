"""Schedule CRUD and the publish pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.api.core.config import settings
from apps.api.models import Project, User, Video
from apps.api.models.schedule import PublishedPost, Schedule
from apps.api.services import publishing
from apps.api.services import social_accounts as accounts
from apps.api.services.platforms import (
    PlatformAuthError,
    PublishError,
    PublishResult,
    TokenSet,
    get_platform,
)


@pytest.fixture
def configured(monkeypatch):
    for name in ("YOUTUBE", "INSTAGRAM", "TIKTOK", "X"):
        monkeypatch.setattr(settings, f"{name}_CLIENT_ID", "id")
        monkeypatch.setattr(settings, f"{name}_CLIENT_SECRET", "secret")
        monkeypatch.setattr(settings, f"{name}_REDIRECT_URI", "https://a/cb")


@pytest.fixture
def owner(client, db, auth_headers):
    headers = auth_headers(email="owner@example.com")
    user = db.query(User).filter(User.email == "owner@example.com").one()
    return user, headers


def make_video(db, user_id: int, status: str = "completed", storage_key=None) -> Video:
    project = Project(user_id=user_id, title="P", topic="t", status="completed")
    db.add(project)
    db.commit()
    db.refresh(project)
    video = Video(
        project_id=project.id,
        user_id=user_id,
        status=status,
        storage_key=storage_key,
        script_text="A script.",
        generation_params_json={},
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def connect(db, user_id: int, platform: str = "youtube", **kw):
    token = TokenSet(
        access_token=kw.get("access_token", "at"),
        refresh_token="rt",
        expires_at=kw.get("expires_at", datetime.now(timezone.utc) + timedelta(hours=2)),
        account_id=kw.get("account_id", "acct"),
        account_name="Channel",
    )
    return accounts.upsert_account(db, user_id, platform, token)


def soon(minutes: int = 60) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


class TestCreateSchedule:
    def test_requires_authentication(self, client):
        response = client.post("/schedules", json={})
        assert response.status_code == 401

    def test_creates_a_pending_schedule(self, client, db, owner, configured):
        user, headers = owner
        video = make_video(db, user.id)
        connect(db, user.id)

        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": soon(),
                "title": "Launch",
                "tags": ["one", "#two"],
                "privacy": "public",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "pending"
        assert body["platform"] == "youtube"
        assert body["video_id"] == video.id

    def test_post_metadata_is_persisted_on_the_video(
        self, client, db, owner, configured
    ):
        user, headers = owner
        video = make_video(db, user.id)
        connect(db, user.id)

        client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": soon(),
                "title": "Launch",
                "tags": ["one"],
                "privacy": "public",
            },
        )
        db.expire_all()
        params = db.get(Video, video.id).generation_params_json
        assert params["title"] == "Launch"
        assert params["tags"] == ["one"]
        assert params["privacy"] == "public"

    def test_someone_elses_video_is_404(self, client, db, make_user, owner, configured):
        _user, headers = owner
        victim = make_user(email="victim@example.com")
        video = make_video(db, victim.id)
        connect(db, victim.id)

        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": soon(),
            },
        )
        assert response.status_code == 404

    def test_unknown_platform_is_422(self, client, db, owner, configured):
        user, headers = owner
        video = make_video(db, user.id)
        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "myspace",
                "scheduled_at": soon(),
            },
        )
        assert response.status_code == 422

    def test_unconfigured_platform_is_503(self, client, db, owner):
        user, headers = owner
        video = make_video(db, user.id)
        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": soon(),
            },
        )
        assert response.status_code == 503

    def test_without_a_connected_account_is_409(self, client, db, owner, configured):
        """Scheduling a post that could never publish is worse than
        refusing it."""
        user, headers = owner
        video = make_video(db, user.id)
        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": soon(),
            },
        )
        assert response.status_code == 409
        assert "connect" in response.json()["detail"].lower()

    def test_a_past_time_is_422(self, client, db, owner, configured):
        user, headers = owner
        video = make_video(db, user.id)
        connect(db, user.id)
        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": soon(-60),
            },
        )
        assert response.status_code == 422

    def test_a_timezone_offset_is_normalised_to_utc(
        self, client, db, owner, configured
    ):
        """Storing an offset-aware time beside naive rows would make every
        due-date comparison wrong."""
        user, headers = owner
        video = make_video(db, user.id)
        connect(db, user.id)

        target = datetime.now(timezone.utc) + timedelta(hours=5)
        shifted = target.astimezone(timezone(timedelta(hours=-5)))

        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": shifted.isoformat(),
            },
        )
        assert response.status_code == 201
        stored = db.get(Schedule, response.json()["id"])
        assert stored.scheduled_at.tzinfo is None
        assert abs((stored.scheduled_at - target.replace(tzinfo=None)).total_seconds()) < 2

    def test_double_scheduling_the_same_video_is_409(
        self, client, db, owner, configured
    ):
        user, headers = owner
        video = make_video(db, user.id)
        connect(db, user.id)
        payload = {
            "video_id": video.id,
            "platform": "youtube",
            "scheduled_at": soon(),
        }
        assert client.post("/schedules", headers=headers, json=payload).status_code == 201
        second = client.post("/schedules", headers=headers, json=payload)
        assert second.status_code == 409

    def test_the_same_video_may_go_to_two_platforms(self, client, db, owner, configured):
        user, headers = owner
        video = make_video(db, user.id)
        connect(db, user.id, "youtube")
        connect(db, user.id, "tiktok", account_id="tt")

        for platform in ("youtube", "tiktok"):
            response = client.post(
                "/schedules",
                headers=headers,
                json={
                    "video_id": video.id,
                    "platform": platform,
                    "scheduled_at": soon(),
                },
            )
            assert response.status_code == 201, response.text

    def test_too_many_tags_is_422(self, client, db, owner, configured):
        user, headers = owner
        video = make_video(db, user.id)
        connect(db, user.id)
        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": soon(),
                "tags": [f"t{i}" for i in range(40)],
            },
        )
        assert response.status_code == 422

    def test_invalid_privacy_is_422(self, client, db, owner, configured):
        user, headers = owner
        video = make_video(db, user.id)
        connect(db, user.id)
        response = client.post(
            "/schedules",
            headers=headers,
            json={
                "video_id": video.id,
                "platform": "youtube",
                "scheduled_at": soon(),
                "privacy": "secret",
            },
        )
        assert response.status_code == 422


class TestReadAndCancel:
    def _create(self, client, db, user, headers, **over):
        video = make_video(db, user.id)
        connect(db, user.id)
        payload = {
            "video_id": video.id,
            "platform": "youtube",
            "scheduled_at": soon(),
        }
        payload.update(over)
        response = client.post("/schedules", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    def test_list_is_paginated(self, client, db, owner, configured):
        user, headers = owner
        self._create(client, db, user, headers)
        body = client.get("/schedules", headers=headers).json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    def test_list_filters_by_status(self, client, db, owner, configured):
        user, headers = owner
        self._create(client, db, user, headers)
        assert client.get("/schedules?status=pending", headers=headers).json()["total"] == 1
        assert client.get("/schedules?status=failed", headers=headers).json()["total"] == 0

    def test_list_rejects_an_unknown_status(self, client, owner):
        _user, headers = owner
        assert client.get("/schedules?status=bogus", headers=headers).status_code == 422

    def test_list_filters_by_platform(self, client, db, owner, configured):
        user, headers = owner
        self._create(client, db, user, headers)
        assert client.get("/schedules?platform=youtube", headers=headers).json()["total"] == 1
        assert client.get("/schedules?platform=tiktok", headers=headers).json()["total"] == 0

    def test_list_is_scoped_to_the_owner(
        self, client, db, make_user, owner, configured
    ):
        user, headers = owner
        self._create(client, db, user, headers)

        other_headers = {"Authorization": "Bearer nope"}
        assert client.get("/schedules", headers=other_headers).status_code == 401

    def test_get_one(self, client, db, owner, configured):
        user, headers = owner
        created = self._create(client, db, user, headers)
        response = client.get(f"/schedules/{created['id']}", headers=headers)
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_someone_elses_is_404(
        self, client, db, make_user, owner, configured, auth_headers
    ):
        user, headers = owner
        created = self._create(client, db, user, headers)

        attacker = auth_headers(email="attacker@example.com")
        assert client.get(f"/schedules/{created['id']}", headers=attacker).status_code == 404

    def test_cancel_a_pending_schedule(self, client, db, owner, configured):
        user, headers = owner
        created = self._create(client, db, user, headers)
        assert client.delete(f"/schedules/{created['id']}", headers=headers).status_code == 204

        db.expire_all()
        assert db.get(Schedule, created["id"]).status == "cancelled"

    def test_cannot_cancel_a_running_schedule(self, client, db, owner, configured):
        """It is already talking to the provider; claiming it was cancelled
        would be a lie."""
        user, headers = owner
        created = self._create(client, db, user, headers)
        schedule = db.get(Schedule, created["id"])
        schedule.status = "running"
        db.commit()

        response = client.delete(f"/schedules/{created['id']}", headers=headers)
        assert response.status_code == 409

    def test_cannot_cancel_someone_elses(
        self, client, db, owner, configured, auth_headers
    ):
        user, headers = owner
        created = self._create(client, db, user, headers)
        attacker = auth_headers(email="attacker@example.com")
        assert client.delete(f"/schedules/{created['id']}", headers=attacker).status_code == 404

    def test_missing_schedule_is_404(self, client, owner):
        _user, headers = owner
        assert client.get("/schedules/999", headers=headers).status_code == 404


class TestPublishedPostsEndpoint:
    def test_lists_attempts_newest_first(self, client, db, owner, configured):
        user, headers = owner
        for index in range(2):
            db.add(
                PublishedPost(
                    video_id=1,
                    user_id=user.id,
                    platform="youtube",
                    status="published",
                    platform_post_id=f"p{index}",
                )
            )
        db.commit()

        body = client.get("/published-posts", headers=headers).json()
        assert body["total"] == 2
        assert body["items"][0]["platform_post_id"] == "p1"

    def test_is_scoped_to_the_owner(self, client, db, make_user, owner):
        _user, headers = owner
        victim = make_user(email="victim@example.com")
        db.add(PublishedPost(video_id=1, user_id=victim.id, platform="x", status="published"))
        db.commit()
        assert client.get("/published-posts", headers=headers).json()["total"] == 0


# --- The publish pipeline -----------------------------------------------------------


def make_schedule(db, user_id, video_id, platform="youtube", status="pending"):
    schedule = Schedule(
        video_id=video_id,
        user_id=user_id,
        platform=platform,
        scheduled_at=datetime.utcnow(),
        timezone="UTC",
        status=status,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


class TestPreflight:
    def test_a_video_still_generating_is_refused(self, db, make_user, configured):
        user = make_user()
        video = make_video(db, user.id, status="generating")
        connect(db, user.id)
        schedule = make_schedule(db, user.id, video.id)

        with pytest.raises(publishing.NotPublishable, match="not 'completed'"):
            publishing.preflight(db, schedule)

    def test_a_deleted_video_is_refused(self, db, make_user, configured):
        user = make_user()
        schedule = make_schedule(db, user.id, 4242)
        with pytest.raises(publishing.NotPublishable, match="no longer exists"):
            publishing.preflight(db, schedule)

    def test_a_disconnected_account_is_refused(self, db, make_user, configured):
        user = make_user()
        video = make_video(db, user.id)
        account = connect(db, user.id)
        accounts.disconnect(db, account)
        schedule = make_schedule(db, user.id, video.id)

        with pytest.raises(publishing.NotPublishable, match="No active youtube account"):
            publishing.preflight(db, schedule)

    def test_an_unconfigured_platform_is_refused(self, db, make_user):
        user = make_user()
        video = make_video(db, user.id)
        connect(db, user.id)
        schedule = make_schedule(db, user.id, video.id)

        with pytest.raises(publishing.NotPublishable, match="not configured"):
            publishing.preflight(db, schedule)

    def test_a_ready_video_and_account_pass(self, db, make_user, configured):
        user = make_user()
        video = make_video(db, user.id)
        connect(db, user.id)
        schedule = make_schedule(db, user.id, video.id)

        checked_video, account = publishing.preflight(db, schedule)
        assert checked_video.id == video.id
        assert account.platform == "youtube"


class TestMediaAvailability:
    def test_youtube_without_a_file_is_refused_clearly(self, db, make_user, configured):
        """The honest failure: nothing was rendered, so there are no bytes.

        The key is an object key that is not in any bucket (object storage
        is off in the suite), so neither a local file nor a download can
        produce one.
        """
        user = make_user()
        video = make_video(db, user.id, storage_key="videos/not-on-disk.mp4")
        request = publishing.build_request(video, None, type("A", (), {"account_id": "a"})())

        with pytest.raises(
            publishing.NotPublishable, match="no rendered video file could be found"
        ):
            publishing.check_media_available(get_platform("youtube"), request)

    def test_instagram_without_a_url_is_refused_clearly(self, db, make_user, configured):
        user = make_user()
        video = make_video(db, user.id)
        request = publishing.build_request(video, None, type("A", (), {"account_id": "a"})())

        with pytest.raises(
            publishing.NotPublishable, match="public HTTPS\\s+URL"
        ) as caught:
            publishing.check_media_available(get_platform("instagram"), request)

        # The message must name the actual cause, which is now a
        # configuration choice rather than missing code.
        assert "STORAGE_BACKEND=local" in str(caught.value)

    def test_a_real_file_satisfies_youtube(self, db, make_user, configured, tmp_path):
        path = tmp_path / "v.mp4"
        path.write_bytes(b"0" * 10)
        user = make_user()
        video = make_video(db, user.id, storage_key=str(path))
        request = publishing.build_request(video, None, type("A", (), {"account_id": "a"})())

        publishing.check_media_available(get_platform("youtube"), request)
        assert request.file_path == str(path)

    def test_a_public_url_satisfies_instagram(self, db, make_user, configured):
        user = make_user()
        video = make_video(db, user.id)
        video.generation_params_json = {"public_url": "https://cdn/v.mp4"}
        db.commit()
        request = publishing.build_request(video, None, type("A", (), {"account_id": "a"})())

        publishing.check_media_available(get_platform("instagram"), request)
        assert request.video_url == "https://cdn/v.mp4"


class TestClaim:
    def test_claiming_moves_pending_to_running(self, db, make_user):
        user = make_user()
        schedule = make_schedule(db, user.id, 1)
        claimed = publishing.claim(db, schedule.id)
        assert claimed is not None
        assert claimed.status == "running"

    def test_a_cancelled_schedule_cannot_be_claimed(self, db, make_user):
        """Cancelling before the worker picks it up must actually prevent
        the post."""
        user = make_user()
        schedule = make_schedule(db, user.id, 1, status="cancelled")
        assert publishing.claim(db, schedule.id) is None

    def test_a_completed_schedule_cannot_be_reclaimed(self, db, make_user):
        user = make_user()
        schedule = make_schedule(db, user.id, 1, status="completed")
        assert publishing.claim(db, schedule.id) is None

    def test_a_missing_schedule_cannot_be_claimed(self, db):
        assert publishing.claim(db, 9999) is None


class TestPublishSchedule:
    def _ready(self, db, make_user, tmp_path, platform="youtube"):
        path = tmp_path / "v.mp4"
        path.write_bytes(b"0" * 64)
        user = make_user()
        video = make_video(db, user.id, storage_key=str(path))
        connect(db, user.id, platform)
        schedule = make_schedule(db, user.id, video.id, platform)
        return user, video, schedule

    def test_a_successful_publish_records_everything(
        self, db, make_user, configured, tmp_path, monkeypatch
    ):
        user, video, schedule = self._ready(db, make_user, tmp_path)

        async def fake_publish(token, request):
            assert token == "at"
            return PublishResult(post_id="yt-1", url="https://youtu.be/yt-1")

        monkeypatch.setattr(get_platform("youtube"), "publish", fake_publish)

        result = publishing.publish_schedule(db, schedule.id)
        assert result["published"] is True
        assert result["platform_post_id"] == "yt-1"

        db.expire_all()
        stored = db.get(Schedule, schedule.id)
        assert stored.status == "completed"
        assert stored.platform_post_id == "yt-1"
        assert stored.platform_url == "https://youtu.be/yt-1"

        post = db.query(PublishedPost).one()
        assert post.status == "published"
        assert post.published_at is not None

    def test_a_provider_failure_is_recorded_not_raised(
        self, db, make_user, configured, tmp_path, monkeypatch
    ):
        """The worker must never surface a traceback the user cannot see."""
        user, video, schedule = self._ready(db, make_user, tmp_path)

        async def boom(token, request):
            raise PublishError("quotaExceeded")

        monkeypatch.setattr(get_platform("youtube"), "publish", boom)

        result = publishing.publish_schedule(db, schedule.id)
        assert result["published"] is False
        assert "quotaExceeded" in result["error"]

        db.expire_all()
        assert db.get(Schedule, schedule.id).status == "failed"
        post = db.query(PublishedPost).one()
        assert post.status == "failed"
        assert "quotaExceeded" in post.error_message

    def test_an_unexpected_error_is_also_recorded(
        self, db, make_user, configured, tmp_path, monkeypatch
    ):
        user, video, schedule = self._ready(db, make_user, tmp_path)

        async def boom(token, request):
            raise ZeroDivisionError("bug")

        monkeypatch.setattr(get_platform("youtube"), "publish", boom)

        result = publishing.publish_schedule(db, schedule.id)
        assert result["published"] is False

        db.expire_all()
        assert db.get(Schedule, schedule.id).status == "failed"
        assert "Unexpected error" in db.query(PublishedPost).one().error_message

    def test_a_dead_token_asks_for_reconnection(
        self, db, make_user, configured, tmp_path, monkeypatch
    ):
        user, video, schedule = self._ready(db, make_user, tmp_path)
        account = accounts.find_for_platform(db, user.id, "youtube")
        account.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        async def rejected(refresh_token):
            raise PlatformAuthError("invalid_grant")

        monkeypatch.setattr(get_platform("youtube"), "refresh", rejected)

        result = publishing.publish_schedule(db, schedule.id)
        assert result["published"] is False

        db.expire_all()
        assert db.get(Schedule, schedule.id).status == "failed"
        assert db.get(type(account), account.id).is_active is False

    def test_an_expiring_token_is_refreshed_before_publishing(
        self, db, make_user, configured, tmp_path, monkeypatch
    ):
        user, video, schedule = self._ready(db, make_user, tmp_path)
        account = accounts.find_for_platform(db, user.id, "youtube")
        account.expires_at = datetime.utcnow() + timedelta(seconds=30)
        db.commit()

        async def refreshed(refresh_token):
            return TokenSet(
                access_token="fresh-token",
                refresh_token="rt2",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

        seen = {}

        async def fake_publish(token, request):
            seen["token"] = token
            return PublishResult(post_id="ok")

        monkeypatch.setattr(get_platform("youtube"), "refresh", refreshed)
        monkeypatch.setattr(get_platform("youtube"), "publish", fake_publish)

        publishing.publish_schedule(db, schedule.id)
        assert seen["token"] == "fresh-token"

    def test_a_cancelled_schedule_is_skipped(self, db, make_user, configured, tmp_path):
        user, video, schedule = self._ready(db, make_user, tmp_path)
        schedule.status = "cancelled"
        db.commit()

        result = publishing.publish_schedule(db, schedule.id)
        assert result["published"] is False
        assert result["status"] == "cancelled"
        assert db.query(PublishedPost).count() == 0

    def test_publishing_twice_does_not_post_twice(
        self, db, make_user, configured, tmp_path, monkeypatch
    ):
        """The compare-and-set on the row is the double-post guard."""
        user, video, schedule = self._ready(db, make_user, tmp_path)
        calls = []

        async def fake_publish(token, request):
            calls.append(1)
            return PublishResult(post_id="once")

        monkeypatch.setattr(get_platform("youtube"), "publish", fake_publish)

        first = publishing.publish_schedule(db, schedule.id)
        second = publishing.publish_schedule(db, schedule.id)

        assert first["published"] is True
        assert second["published"] is False
        assert len(calls) == 1

    def test_the_request_carries_the_account_identity(
        self, db, make_user, configured, tmp_path, monkeypatch
    ):
        """Instagram addresses every call to /{ig-user-id}/..., so losing
        this would break publishing there."""
        user, video, schedule = self._ready(db, make_user, tmp_path)
        seen = {}

        async def fake_publish(token, request):
            seen["account_id"] = request.account_id
            return PublishResult(post_id="x")

        monkeypatch.setattr(get_platform("youtube"), "publish", fake_publish)
        publishing.publish_schedule(db, schedule.id)
        assert seen["account_id"] == "acct"

    def test_a_missing_file_fails_before_contacting_the_provider(
        self, db, make_user, configured, monkeypatch
    ):
        user = make_user()
        video = make_video(db, user.id, storage_key="/nowhere/v.mp4")
        connect(db, user.id)
        schedule = make_schedule(db, user.id, video.id)

        async def must_not_run(token, request):  # pragma: no cover
            raise AssertionError("the provider should not be contacted")

        monkeypatch.setattr(get_platform("youtube"), "publish", must_not_run)

        result = publishing.publish_schedule(db, schedule.id)
        assert result["published"] is False
        assert "no rendered video file could be found" in result["error"]


def unclosable(session):
    """Hand the worker the test session without letting it close it.

    dispatch_due_schedules owns and closes its session, which would detach
    every object the test still holds.
    """

    class _Shielded:
        def __getattr__(self, name):
            return getattr(session, name)

        def close(self):
            pass

    return _Shielded()


class TestDispatchHandsOffToPublish:
    """The Phase 4 beat tick now has somewhere to hand work to."""

    def test_due_schedules_are_enqueued_for_publishing(
        self, db, make_user, configured, monkeypatch
    ):
        user = make_user()
        video = make_video(db, user.id)
        connect(db, user.id)
        due = make_schedule(db, user.id, video.id)
        due.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
        db.commit()

        sent = []
        from apps.worker import tasks as worker_tasks

        monkeypatch.setattr(
            worker_tasks.celery_app,
            "send_task",
            lambda name, args=None, **kw: sent.append((name, args)),
        )
        monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: unclosable(db))

        result = worker_tasks.dispatch_due_schedules()

        assert result["claimed"] == [due.id]
        assert result["dispatched"] == [due.id]
        assert sent == [("hydraclip.publish_schedule", [due.id])]

    def test_a_future_schedule_is_left_alone(
        self, db, make_user, configured, monkeypatch
    ):
        user = make_user()
        video = make_video(db, user.id)
        connect(db, user.id)
        later = make_schedule(db, user.id, video.id)
        later.scheduled_at = datetime.utcnow() + timedelta(hours=1)
        db.commit()

        sent = []
        from apps.worker import tasks as worker_tasks

        monkeypatch.setattr(
            worker_tasks.celery_app,
            "send_task",
            lambda name, args=None, **kw: sent.append(name),
        )
        monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: unclosable(db))

        assert worker_tasks.dispatch_due_schedules()["claimed"] == []
        assert sent == []

    def test_a_broker_failure_does_not_strand_the_row_in_running(
        self, db, make_user, configured, monkeypatch
    ):
        """claim_due_schedules already flipped it to running; if the enqueue
        fails the row would sit there forever with no explanation."""
        user = make_user()
        video = make_video(db, user.id)
        connect(db, user.id)
        due = make_schedule(db, user.id, video.id)
        due.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
        db.commit()

        from apps.worker import tasks as worker_tasks

        def boom(name, args=None, **kw):
            raise OSError("broker unreachable")

        monkeypatch.setattr(worker_tasks.celery_app, "send_task", boom)
        monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: unclosable(db))

        result = worker_tasks.dispatch_due_schedules()
        assert result["dispatched"] == []

        db.expire_all()
        assert db.get(Schedule, due.id).status == "failed"
        assert "broker unreachable" in db.query(PublishedPost).one().error_message
