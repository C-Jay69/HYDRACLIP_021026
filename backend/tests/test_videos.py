"""Video reads, edits, deletion and quota reporting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.api.models import Plan, Project, Subscription, UsageEvent, Video, VideoJob
from apps.api.services import quota as quota_service


def _project(db, user_id: int, title: str = "Project") -> Project:
    project = Project(user_id=user_id, title=title, status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _video(db, project: Project, **kwargs) -> Video:
    video = Video(
        project_id=project.id,
        user_id=project.user_id,
        status=kwargs.pop("status", "completed"),
        **kwargs,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def _login(client, email: str) -> dict[str, str]:
    from tests.conftest import VALID_PASSWORD

    response = client.post("/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# --- Listing -------------------------------------------------------------------


def test_list_returns_only_own_videos(client, auth_headers, make_user, db):
    other = make_user(email="other@example.com")
    _video(db, _project(db, other.id, "Theirs"))

    headers = auth_headers(email="me@example.com")
    me = db.query(Video).count()
    assert me == 1  # the other user's video exists in the table

    body = client.get("/videos", headers=headers).json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_videos_requires_authentication(client):
    assert client.get("/videos").status_code == 401


def test_list_filters_by_status(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    project = _project(db, user.id)
    _video(db, project, status="completed")
    _video(db, project, status="failed")

    headers = _login(client, "me@example.com")
    body = client.get("/videos?status=failed", headers=headers).json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "failed"


def test_list_rejects_unknown_status(client, auth_headers):
    headers = auth_headers()
    response = client.get("/videos?status=banana", headers=headers)
    assert response.status_code == 422


def test_list_filters_by_project(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    first = _project(db, user.id, "First")
    second = _project(db, user.id, "Second")
    _video(db, first)
    _video(db, second)

    headers = _login(client, "me@example.com")
    body = client.get(f"/videos?project_id={second.id}", headers=headers).json()
    assert body["total"] == 1
    assert body["items"][0]["project_id"] == second.id


def test_no_public_video_creation_endpoint(client, auth_headers):
    """Videos must come from the pipeline so quota is always accounted for."""
    headers = auth_headers()
    response = client.post("/videos", json={"project_id": 1}, headers=headers)
    assert response.status_code == 405


# --- Retrieval -------------------------------------------------------------------


def test_get_own_video(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    video = _video(db, _project(db, user.id), script_text="Hello world")

    headers = _login(client, "me@example.com")
    response = client.get(f"/videos/{video.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["script_text"] == "Hello world"


def test_get_other_users_video_returns_404_not_403(client, auth_headers, make_user, db):
    victim = make_user(email="victim@example.com")
    video = _video(db, _project(db, victim.id))

    headers = auth_headers(email="attacker@example.com")
    existing = client.get(f"/videos/{video.id}", headers=headers)
    missing = client.get("/videos/99999", headers=headers)

    assert existing.status_code == 404
    assert existing.json() == missing.json()


def test_admin_can_read_any_video(client, auth_headers, make_user, db):
    owner = make_user(email="owner@example.com")
    video = _video(db, _project(db, owner.id))

    headers = auth_headers(email="admin@example.com", role="ADMIN")
    assert client.get(f"/videos/{video.id}", headers=headers).status_code == 200


# --- Updates ---------------------------------------------------------------------


def test_patch_edits_script(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    video = _video(db, _project(db, user.id), status="pending", script_text="Draft")

    headers = _login(client, "me@example.com")
    response = client.patch(
        f"/videos/{video.id}", json={"script_text": "Corrected"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["script_text"] == "Corrected"


def test_patch_cannot_change_status_or_storage_key(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    video = _video(db, _project(db, user.id), status="failed")

    headers = _login(client, "me@example.com")
    response = client.patch(
        f"/videos/{video.id}",
        json={"status": "completed", "storage_key": "anything"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["storage_key"] is None


def test_patch_rejected_while_generating(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    video = _video(db, _project(db, user.id), status="generating")

    headers = _login(client, "me@example.com")
    response = client.patch(
        f"/videos/{video.id}", json={"script_text": "Too late"}, headers=headers
    )
    assert response.status_code == 409


def test_patch_other_users_video_returns_404(client, auth_headers, make_user, db):
    victim = make_user(email="victim@example.com")
    video = _video(db, _project(db, victim.id), script_text="Original")

    headers = auth_headers(email="attacker@example.com")
    response = client.patch(
        f"/videos/{video.id}", json={"script_text": "Defaced"}, headers=headers
    )
    assert response.status_code == 404

    db.expire_all()
    assert db.get(Video, video.id).script_text == "Original"


# --- Deletion ---------------------------------------------------------------------


def test_delete_removes_video_and_jobs(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    video = _video(db, _project(db, user.id))
    db.add(VideoJob(video_id=video.id, job_type="generate", status="completed"))
    db.commit()

    video_id = video.id
    headers = _login(client, "me@example.com")
    assert client.delete(f"/videos/{video_id}", headers=headers).status_code == 204

    db.expire_all()
    assert db.get(Video, video_id) is None
    assert db.query(VideoJob).filter_by(video_id=video_id).count() == 0


def test_delete_rejected_while_generating(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    video = _video(db, _project(db, user.id), status="generating")

    headers = _login(client, "me@example.com")
    assert client.delete(f"/videos/{video.id}", headers=headers).status_code == 409


def test_delete_does_not_refund_quota(client, auth_headers, make_user, db):
    """Usage is metered per period; deleting a render must not free an allowance."""
    user = make_user(email="me@example.com")
    video = _video(db, _project(db, user.id))
    quota_service.record_video_generated(db, user.id, video_id=video.id)
    db.commit()

    before = quota_service.get_quota(db, user.id).used

    headers = _login(client, "me@example.com")
    client.delete(f"/videos/{video.id}", headers=headers)

    assert quota_service.get_quota(db, user.id).used == before


def test_delete_other_users_video_returns_404(client, auth_headers, make_user, db):
    victim = make_user(email="victim@example.com")
    video = _video(db, _project(db, victim.id))

    headers = auth_headers(email="attacker@example.com")
    assert client.delete(f"/videos/{video.id}", headers=headers).status_code == 404
    db.expire_all()
    assert db.get(Video, video.id) is not None


# --- Jobs ---------------------------------------------------------------------------


def test_list_video_jobs_newest_first(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    video = _video(db, _project(db, user.id))
    db.add_all(
        [
            VideoJob(video_id=video.id, job_type="generate", status="completed"),
            VideoJob(video_id=video.id, job_type="regenerate", status="failed"),
        ]
    )
    db.commit()

    headers = _login(client, "me@example.com")
    jobs = client.get(f"/videos/{video.id}/jobs", headers=headers).json()
    assert len(jobs) == 2
    assert jobs[0]["id"] > jobs[1]["id"]


def test_list_jobs_of_other_users_video_returns_404(client, auth_headers, make_user, db):
    victim = make_user(email="victim@example.com")
    video = _video(db, _project(db, victim.id))

    headers = auth_headers(email="attacker@example.com")
    assert client.get(f"/videos/{video.id}/jobs", headers=headers).status_code == 404


# --- Quota ----------------------------------------------------------------------------


def test_quota_defaults_to_free_plan(client, auth_headers):
    headers = auth_headers()
    body = client.get("/videos/quota", headers=headers).json()

    assert body["plan_name"] == "Free"
    assert body["limit_monthly"] == 3
    assert body["used"] == 0
    assert body["remaining"] == 3
    assert body["unlimited"] is False


def test_quota_route_is_not_shadowed_by_the_id_route(client, auth_headers):
    """`/videos/quota` must not be parsed as `/videos/{video_id}`."""
    headers = auth_headers()
    assert client.get("/videos/quota", headers=headers).status_code == 200


def test_quota_counts_usage_events(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    for _ in range(2):
        quota_service.record_video_generated(db, user.id)
    db.commit()

    headers = _login(client, "me@example.com")
    body = client.get("/videos/quota", headers=headers).json()
    assert body["used"] == 2
    assert body["remaining"] == 1


def test_quota_ignores_other_users_usage(client, auth_headers, make_user, db):
    other = make_user(email="other@example.com")
    quota_service.record_video_generated(db, other.id)
    db.commit()

    headers = auth_headers(email="me@example.com")
    assert client.get("/videos/quota", headers=headers).json()["used"] == 0


def test_quota_ignores_events_outside_the_period(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    db.add(
        UsageEvent(
            user_id=user.id,
            event_type=quota_service.EVENT_VIDEO_GENERATED,
            quantity=1,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
    )
    db.commit()

    headers = _login(client, "me@example.com")
    assert client.get("/videos/quota", headers=headers).json()["used"] == 0


def test_quota_uses_active_subscription_plan(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    plan = Plan(
        name="Pro",
        stripe_price_id="price_pro",
        video_limit_monthly=50,
        is_active=True,
    )
    db.add(plan)
    db.flush()

    now = datetime.now(timezone.utc)
    db.add(
        Subscription(
            user_id=user.id,
            plan_id=plan.id,
            stripe_subscription_id=f"sub_{user.id}_{plan.id}",
            status="active",
            current_period_start=now - timedelta(days=5),
            current_period_end=now + timedelta(days=25),
        )
    )
    db.commit()

    headers = _login(client, "me@example.com")
    body = client.get("/videos/quota", headers=headers).json()
    assert body["plan_name"] == "Pro"
    assert body["limit_monthly"] == 50
    assert body["remaining"] == 50


def test_zero_limit_means_unlimited(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    plan = Plan(
        name="Enterprise",
        stripe_price_id="price_ent",
        video_limit_monthly=0,
        is_active=True,
    )
    db.add(plan)
    db.flush()

    now = datetime.now(timezone.utc)
    db.add(
        Subscription(
            user_id=user.id,
            plan_id=plan.id,
            stripe_subscription_id=f"sub_{user.id}_{plan.id}",
            status="active",
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=29),
        )
    )
    db.commit()

    headers = _login(client, "me@example.com")
    body = client.get("/videos/quota", headers=headers).json()
    assert body["unlimited"] is True
    assert body["remaining"] is None


def test_cancelled_subscription_falls_back_to_free(client, auth_headers, make_user, db):
    user = make_user(email="me@example.com")
    plan = Plan(
        name="Pro",
        stripe_price_id="price_pro",
        video_limit_monthly=50,
        is_active=True,
    )
    db.add(plan)
    db.flush()

    now = datetime.now(timezone.utc)
    db.add(
        Subscription(
            user_id=user.id,
            plan_id=plan.id,
            stripe_subscription_id=f"sub_{user.id}_{plan.id}",
            status="cancelled",
            current_period_start=now - timedelta(days=5),
            current_period_end=now + timedelta(days=25),
        )
    )
    db.commit()

    headers = _login(client, "me@example.com")
    assert client.get("/videos/quota", headers=headers).json()["plan_name"] == "Free"
