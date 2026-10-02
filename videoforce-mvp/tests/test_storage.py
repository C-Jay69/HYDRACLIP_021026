"""Object storage for rendered media.

Unlike the platform and stock providers, this one is tested against a
*real* S3 server: moto's threaded server speaks HTTP on a local port, so
presigned URLs are genuinely fetched over the wire rather than asserted
about. That matters here, because the whole point of this layer is
producing a URL some other machine can GET.

One honest limitation: moto does not verify presigned signatures, so these
tests prove the URL is well-formed, correctly hosted and serves the right
bytes with the right content type -- not that tampering is rejected. Real
MinIO and S3 both enforce the signature.
"""

from __future__ import annotations

import socket
import threading
from pathlib import Path

import pytest
import requests

from apps.api.core.config import settings
from apps.api.services import storage as storage_service
from apps.api.services.storage import (
    ObjectStorage,
    StorageError,
    StorageNotConfigured,
    content_type_for,
    is_object_key,
    media_key,
)

moto_server = pytest.importorskip("moto.server", reason="moto[server] not installed")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def s3_endpoint():
    """A real S3 server on a local port."""
    port = _free_port()
    server = moto_server.ThreadedMotoServer(port=port, verbose=False)
    server.start()
    yield f"http://127.0.0.1:{port}"
    server.stop()


@pytest.fixture
def storage(s3_endpoint, monkeypatch):
    """Storage pointed at the live moto server, with a per-test bucket."""
    bucket = f"vf-test-{threading.get_ident()}"
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "MINIO_ENDPOINT", s3_endpoint)
    monkeypatch.setattr(settings, "MINIO_ACCESS_KEY", "test-key")
    monkeypatch.setattr(settings, "MINIO_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "MINIO_BUCKET", bucket)
    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "")
    monkeypatch.setattr(settings, "S3_FORCE_PATH_STYLE", True)

    instance = ObjectStorage()
    storage_service.reset_storage()
    monkeypatch.setattr(storage_service, "_storage", instance)
    yield instance
    storage_service.reset_storage()


@pytest.fixture
def video_file(tmp_path):
    path = tmp_path / "render.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"fake-video-payload" * 50)
    return path


# --- Configuration ------------------------------------------------------------


def test_storage_is_off_by_default(monkeypatch):
    """A fresh checkout must work with no object store running."""
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    instance = ObjectStorage()

    assert instance.enabled is False
    reason = instance.configuration_error()
    assert reason is not None
    assert "STORAGE_BACKEND=local" in reason


def test_missing_credentials_are_named(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "MINIO_ACCESS_KEY", "")
    instance = ObjectStorage()

    reason = instance.configuration_error()
    assert reason is not None
    assert "MINIO_ACCESS_KEY" in reason


def test_operations_refuse_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    instance = ObjectStorage()

    with pytest.raises(StorageNotConfigured):
        instance.upload(tmp_path / "x.mp4", "k")


# --- The internal/public endpoint distinction ---------------------------------


def test_internal_endpoint_is_flagged_as_unreachable(monkeypatch):
    """The failure this whole module exists to prevent.

    A URL signed against http://minio:9000 carries that host in the
    signature; Instagram gets a DNS failure, not a video.
    """
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "")

    warning = ObjectStorage().external_url_warning()

    assert warning is not None
    assert "MEDIA_PUBLIC_BASE_URL" in warning
    assert "Instagram" in warning


def test_plain_http_public_base_is_flagged(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "http://cdn.example.com")

    warning = ObjectStorage().external_url_warning()

    assert warning is not None
    assert "HTTPS" in warning


def test_https_public_base_has_no_warning(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "https://cdn.example.com")

    assert ObjectStorage().external_url_warning() is None


def test_urls_are_signed_against_the_public_host(storage, video_file, monkeypatch):
    """Signing must use the public endpoint, not a string replacement."""
    storage.upload(video_file, "videos/1/1/a.mp4")

    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "https://cdn.example.com")
    storage.reset()

    url = storage.url_for("videos/1/1/a.mp4")

    assert url.startswith("https://cdn.example.com/")
    assert "X-Amz-Signature" in url or "Signature" in url


# --- Upload and fetch ---------------------------------------------------------


def test_upload_creates_the_bucket_on_demand(storage, video_file):
    """A freshly provisioned MinIO has no buckets."""
    stored = storage.upload(video_file, "videos/1/1/render.mp4")

    assert stored.key == "videos/1/1/render.mp4"
    assert stored.size_bytes == video_file.stat().st_size
    assert stored.content_type == "video/mp4"
    assert storage.exists("videos/1/1/render.mp4")


def test_a_presigned_url_actually_serves_the_file(storage, video_file):
    """The point of the whole module, verified over real HTTP."""
    stored = storage.upload(video_file, "videos/2/5/render.mp4")

    response = requests.get(stored.url, timeout=10)

    assert response.status_code == 200
    assert response.content == video_file.read_bytes()
    # Providers check this before downloading.
    assert response.headers["Content-Type"] == "video/mp4"


def test_uploading_a_missing_file_is_an_error(storage, tmp_path):
    with pytest.raises(StorageError, match="does not exist"):
        storage.upload(tmp_path / "nope.mp4", "k")


def test_uploading_an_empty_file_is_an_error(storage, tmp_path):
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")

    with pytest.raises(StorageError, match="empty"):
        storage.upload(empty, "k")


def test_download_brings_the_bytes_back(storage, video_file, tmp_path):
    """YouTube and X upload bytes, so the worker must be able to re-fetch."""
    storage.upload(video_file, "videos/1/1/render.mp4")

    fetched = storage.download("videos/1/1/render.mp4", tmp_path / "back.mp4")

    assert fetched.read_bytes() == video_file.read_bytes()


def test_delete_removes_the_object(storage, video_file):
    storage.upload(video_file, "videos/1/1/render.mp4")
    storage.delete("videos/1/1/render.mp4")

    assert storage.exists("videos/1/1/render.mp4") is False


def test_expiry_is_carried_in_the_url(storage, video_file):
    storage.upload(video_file, "videos/1/1/render.mp4")

    url = storage.url_for("videos/1/1/render.mp4", expires_in=120)

    assert "Expires=" in url or "X-Amz-Expires=120" in url


# --- Keys ---------------------------------------------------------------------


def test_media_keys_are_namespaced_by_user_and_video():
    key = media_key(video_id=7, user_id=3, filename="video_abc.mp4")
    assert key == "videos/3/7/video_abc.mp4"


def test_media_keys_cannot_be_escaped_by_the_filename():
    """A traversing filename must not climb out of the prefix."""
    key = media_key(video_id=7, user_id=3, filename="../../../etc/passwd")
    assert key == "videos/3/7/passwd"
    assert ".." not in key


def test_object_keys_are_told_apart_from_local_paths():
    assert is_object_key("videos/3/7/a.mp4") is True
    assert is_object_key("/tmp/videoforce/video_abc.mp4") is False
    assert is_object_key(None) is False
    assert is_object_key("") is False


def test_content_types_cover_what_we_store():
    assert content_type_for("a.mp4") == "video/mp4"
    assert content_type_for("a.srt") == "application/x-subrip"
    assert content_type_for("a.unknown") == "application/octet-stream"


# --- Resolution helpers -------------------------------------------------------


def test_local_copy_returns_an_existing_local_path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    path = tmp_path / "v.mp4"
    path.write_bytes(b"data")

    assert storage_service.local_copy(str(path)) == path


def test_local_copy_is_none_for_a_vanished_file(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    assert storage_service.local_copy("/nowhere/at/all.mp4") is None


def test_local_copy_fetches_an_object_back(storage, video_file, tmp_path):
    storage.upload(video_file, "videos/1/1/render.mp4")

    fetched = storage_service.local_copy(
        "videos/1/1/render.mp4", work_dir=tmp_path / "work"
    )

    assert fetched is not None
    assert fetched.read_bytes() == video_file.read_bytes()


def test_local_copy_reuses_an_already_fetched_file(storage, video_file, tmp_path):
    storage.upload(video_file, "videos/1/1/render.mp4")
    work = tmp_path / "work"

    first = storage_service.local_copy("videos/1/1/render.mp4", work_dir=work)
    storage.delete("videos/1/1/render.mp4")
    second = storage_service.local_copy("videos/1/1/render.mp4", work_dir=work)

    assert first == second
    assert second is not None


def test_public_url_prefers_a_recorded_one(storage):
    """A recorded URL may point at a CDN this process knows nothing about."""
    url = storage_service.public_url(
        "videos/1/1/a.mp4", recorded="https://cdn.example.com/custom.mp4"
    )
    assert url == "https://cdn.example.com/custom.mp4"


def test_public_url_is_none_for_a_local_path(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    assert storage_service.public_url("/tmp/videoforce/x.mp4") is None


def test_public_url_signs_an_object_key(storage, video_file):
    storage.upload(video_file, "videos/1/1/render.mp4")

    url = storage_service.public_url("videos/1/1/render.mp4")

    assert url is not None
    assert requests.get(url, timeout=10).status_code == 200
