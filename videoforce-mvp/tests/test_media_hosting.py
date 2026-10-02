"""The render -> bucket -> publishable URL path.

This is the integration that was missing: assembly wrote an MP4 to a
worker's disk, and Instagram and TikTok fetch by URL, so neither could ever
publish. These tests run a real S3 server and check that a stored render
produces a URL a provider can actually GET.
"""

from __future__ import annotations

import socket

import pytest
import requests

from apps.api.core.config import settings
from apps.api.models import Project, Video
from apps.api.services import jobs as job_service
from apps.api.services import publishing
from apps.api.services import storage as storage_service
from apps.api.services.platforms import get_platform

moto_server = pytest.importorskip("moto.server", reason="moto[server] not installed")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def s3_endpoint():
    port = _free_port()
    server = moto_server.ThreadedMotoServer(port=port, verbose=False)
    server.start()
    yield f"http://127.0.0.1:{port}"
    server.stop()


@pytest.fixture
def object_storage(s3_endpoint, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "MINIO_ENDPOINT", s3_endpoint)
    monkeypatch.setattr(settings, "MINIO_ACCESS_KEY", "k")
    monkeypatch.setattr(settings, "MINIO_SECRET_KEY", "s")
    monkeypatch.setattr(settings, "MINIO_BUCKET", "videoforce-media")
    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "")
    storage_service.reset_storage()
    instance = storage_service.ObjectStorage()
    monkeypatch.setattr(storage_service, "_storage", instance)
    yield instance
    storage_service.reset_storage()


@pytest.fixture
def rendered_file(tmp_path):
    path = tmp_path / "video_abc123.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"payload" * 200)
    return path


def make_video(db, user_id, status="completed", **kwargs):
    """Videos require a project; mirrors the helper in test_schedules."""
    project = Project(user_id=user_id, title="P", topic="t", status="completed")
    db.add(project)
    db.commit()
    db.refresh(project)
    video = Video(
        project_id=project.id,
        user_id=user_id,
        status=status,
        script_text="A script.",
        generation_params_json=kwargs.pop("generation_params_json", {}),
        **kwargs,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


class _Account:
    account_id = "acct-1"


# --- The upload step ----------------------------------------------------------


def test_render_is_uploaded_and_the_key_is_stored(object_storage, rendered_file):
    rendered = {"video_path": str(rendered_file), "status": "rendered"}

    stored = job_service._store_render(rendered, video_id=7, user_id=3)

    assert stored is not None
    assert stored["key"] == "videos/3/7/video_abc123.mp4"
    assert object_storage.exists(stored["key"])
    assert requests.get(stored["url"], timeout=10).status_code == 200


def test_scratch_file_is_removed_after_upload(object_storage, rendered_file):
    """The worker's disk is not where finished videos should live."""
    rendered = {"video_path": str(rendered_file)}

    job_service._store_render(rendered, video_id=1, user_id=1)

    assert not rendered_file.exists()


def test_scratch_file_is_kept_when_asked(object_storage, rendered_file, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_RETAIN_LOCAL", True)
    rendered = {"video_path": str(rendered_file)}

    job_service._store_render(rendered, video_id=1, user_id=1)

    assert rendered_file.exists()


def test_upload_is_skipped_when_storage_is_off(monkeypatch, rendered_file):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    storage_service.reset_storage()
    rendered = {"video_path": str(rendered_file)}

    assert job_service._store_render(rendered, video_id=1, user_id=1) is None
    # The render survives on disk, which is the whole point of the fallback.
    assert rendered_file.exists()


def test_a_failed_upload_warns_but_keeps_the_render(
    object_storage, rendered_file, monkeypatch
):
    """Losing several minutes of rendering over a transient S3 error would
    be a bad trade."""

    def explode(*args, **kwargs):
        raise storage_service.StorageError("bucket is on fire")

    monkeypatch.setattr(object_storage, "upload", explode)
    rendered = {"video_path": str(rendered_file)}

    assert job_service._store_render(rendered, video_id=1, user_id=1) is None
    assert rendered_file.exists()
    assert any("Upload to object storage failed" in w for w in rendered["warnings"])


def test_an_unreachable_public_endpoint_is_warned_about(
    object_storage, rendered_file, monkeypatch
):
    monkeypatch.setattr(settings, "MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "")
    rendered = {"video_path": str(rendered_file)}

    # Upload itself is mocked out; we only care about the caveat.
    monkeypatch.setattr(
        object_storage,
        "upload",
        lambda *a, **k: storage_service.StoredObject(
            key="videos/1/1/x.mp4", bucket="b", size_bytes=1, content_type="video/mp4"
        ),
    )

    job_service._store_render(rendered, video_id=1, user_id=1)

    assert any("MEDIA_PUBLIC_BASE_URL" in w for w in rendered.get("warnings", []))


# --- What publishing now sees -------------------------------------------------


def test_instagram_can_now_be_published(object_storage, rendered_file, db, make_user):
    """The blocker this change exists to remove."""
    user = make_user()
    key = storage_service.media_key(1, user.id, rendered_file.name)
    object_storage.upload(rendered_file, key)
    video = make_video(db, user.id, storage_key=key)

    request = publishing.build_request(video, None, _Account())

    assert request.video_url is not None
    # check_media_available must no longer refuse.
    publishing.check_media_available(get_platform("instagram"), request)
    # And the URL must really serve the video.
    response = requests.get(request.video_url, timeout=10)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "video/mp4"


def test_tiktok_can_now_be_published(object_storage, rendered_file, db, make_user):
    user = make_user()
    key = storage_service.media_key(2, user.id, rendered_file.name)
    object_storage.upload(rendered_file, key)
    video = make_video(db, user.id, storage_key=key)

    request = publishing.build_request(video, None, _Account())

    publishing.check_media_available(get_platform("tiktok"), request)
    assert request.video_url is not None


def test_youtube_gets_bytes_back_from_the_bucket(
    object_storage, rendered_file, db, make_user
):
    """The scratch copy is gone after upload, so the worker must re-fetch."""
    user = make_user()
    original = rendered_file.read_bytes()
    key = storage_service.media_key(3, user.id, rendered_file.name)
    object_storage.upload(rendered_file, key)
    rendered_file.unlink()

    video = make_video(db, user.id, storage_key=key)
    request = publishing.build_request(video, None, _Account())

    publishing.check_media_available(get_platform("youtube"), request)
    assert request.file_path is not None
    from pathlib import Path

    assert Path(request.file_path).read_bytes() == original


def test_a_recorded_url_wins_over_a_signed_one(
    object_storage, rendered_file, db, make_user
):
    """A CDN URL recorded on the video may point somewhere this process
    knows nothing about."""
    user = make_user()
    key = storage_service.media_key(4, user.id, rendered_file.name)
    object_storage.upload(rendered_file, key)
    video = make_video(
        db,
        user.id,
        storage_key=key,
        generation_params_json={"public_url": "https://cdn.example.com/v.mp4"},
    )

    request = publishing.build_request(video, None, _Account())

    assert request.video_url == "https://cdn.example.com/v.mp4"


def test_local_only_render_still_refuses_instagram(db, make_user, tmp_path, monkeypatch):
    """With storage off, the honest answer is still no."""
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    storage_service.reset_storage()
    path = tmp_path / "v.mp4"
    path.write_bytes(b"data")
    user = make_user()
    video = make_video(db, user.id, storage_key=str(path))

    request = publishing.build_request(video, None, _Account())

    assert request.file_path == str(path)
    assert request.video_url is None
    with pytest.raises(publishing.NotPublishable, match="STORAGE_BACKEND=local"):
        publishing.check_media_available(get_platform("instagram"), request)


# --- The media endpoint -------------------------------------------------------


def test_media_endpoint_returns_a_working_url(
    object_storage, rendered_file, client, auth_headers, db
):
    headers = auth_headers()
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    key = storage_service.media_key(9, user_id, rendered_file.name)
    object_storage.upload(rendered_file, key)
    video = make_video(db, user_id, storage_key=key)

    body = client.get(f"/videos/{video.id}/media", headers=headers).json()

    assert body["storage"] == "s3"
    assert body["url"] is not None
    assert body["content_type"] == "video/mp4"
    assert requests.get(body["url"], timeout=10).status_code == 200


def test_media_endpoint_explains_an_unrendered_video(
    object_storage, client, auth_headers, db
):
    headers = auth_headers()
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    video = make_video(db, user_id, status="draft")

    body = client.get(f"/videos/{video.id}/media", headers=headers).json()

    assert body["url"] is None
    assert "not been rendered" in body["reason"]


def test_media_endpoint_explains_local_only_storage(
    client, auth_headers, db, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    storage_service.reset_storage()
    headers = auth_headers()
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    video = make_video(db, user_id, storage_key=str(tmp_path / "v.mp4"))

    body = client.get(f"/videos/{video.id}/media", headers=headers).json()

    assert body["url"] is None
    assert "STORAGE_BACKEND=s3" in body["reason"]


def test_media_endpoint_requires_authentication(client, db, make_user):
    user = make_user()
    video = make_video(db, user.id)

    assert client.get(f"/videos/{video.id}/media").status_code == 401


def test_media_endpoint_does_not_leak_another_users_video(
    client, auth_headers, db, make_user
):
    owner = make_user(email="owner@example.com")
    video = make_video(db, owner.id, storage_key="videos/1/1/x.mp4")
    headers = auth_headers(email="intruder@example.com")

    assert client.get(f"/videos/{video.id}/media", headers=headers).status_code == 404


# --- Pipeline status ----------------------------------------------------------


def test_pipeline_status_reports_storage(object_storage, client, auth_headers):
    body = client.get("/pipeline/status", headers=auth_headers()).json()

    assert body["media_storage"]["backend"] == "s3"
    assert body["media_storage"]["configured"] is True
    assert body["media_storage"]["public_urls"] is True


def test_pipeline_status_reports_storage_off(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    storage_service.reset_storage()

    body = client.get("/pipeline/status", headers=auth_headers()).json()

    assert body["media_storage"]["backend"] == "local"
    assert body["media_storage"]["public_urls"] is False
    assert "STORAGE_BACKEND=local" in body["media_storage"]["reason"]
