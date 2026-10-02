"""Object storage for rendered media.

Assembly writes an MP4 to the worker's scratch disk. That is fine for
YouTube and X, which upload bytes, but Instagram and TikTok do not accept
bytes at all -- they take a URL and fetch the file themselves. A file on a
worker's local disk has no URL, which is why publishing to those two could
never work no matter how good the render was.

This module uploads finished media to an S3-compatible bucket and issues
URLs a third party can actually fetch.

The subtlety that makes or breaks it
------------------------------------

``MINIO_ENDPOINT`` is usually something like ``http://minio:9000`` -- a
hostname that exists only inside the Docker network. A URL signed against
that endpoint carries that host in both the URL *and* the signature, so
handing it to Instagram produces a DNS failure on their side, not a
download.

So two endpoints are kept apart on purpose:

* **internal** (``MINIO_ENDPOINT``) for uploads, which happen from inside
  the network;
* **public** (``MEDIA_PUBLIC_BASE_URL``) for signing URLs that leave the
  building.

When no public base is configured the internal one is used and
:meth:`ObjectStorage.external_url_warning` says plainly that the result
will not be fetchable from the internet, rather than letting it fail later
as an opaque provider error.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from apps.api.core.config import settings

logger = logging.getLogger(__name__)

LOCAL = "local"
S3 = "s3"

#: Extensions we expect to store, mapped to the content type a provider
#: needs to see. Relying on mimetypes alone is fragile across platforms.
CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".srt": "application/x-subrip",
    ".ass": "text/x-ssa",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class StorageError(RuntimeError):
    """An object-store operation failed."""


class StorageNotConfigured(StorageError):
    """Object storage is not switched on, or is missing credentials."""


@dataclass
class StoredObject:
    """The result of putting a file in the bucket."""

    key: str
    bucket: str
    size_bytes: int
    content_type: str
    url: str | None = None
    """A URL a third party can fetch, when one could be produced."""

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "bucket": self.bucket,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "url": self.url,
        }


def content_type_for(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in CONTENT_TYPES:
        return CONTENT_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def media_key(video_id: int, user_id: int, filename: str) -> str:
    """Where a video lives in the bucket.

    Keyed by user then video so a bucket listing is navigable and a
    per-user lifecycle rule is possible later. The filename keeps the
    render's random component, so re-rendering a video does not overwrite
    the copy a provider may still be fetching.
    """
    safe = Path(filename).name
    return f"videos/{user_id}/{video_id}/{safe}"


class ObjectStorage:
    """S3-compatible object storage."""

    def __init__(self) -> None:
        self._client = None
        self._public_client = None
        self._lock = threading.Lock()
        self._bucket_checked = False

    # --- Readiness -----------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return (settings.STORAGE_BACKEND or LOCAL).strip().lower() == S3

    def configuration_error(self) -> str | None:
        """Why uploads cannot run, or None when they can."""
        if not self.enabled:
            return (
                "object storage is off (STORAGE_BACKEND=local), so rendered "
                "files stay on the worker's local disk"
            )
        missing = [
            name
            for name, value in (
                ("MINIO_ENDPOINT", settings.MINIO_ENDPOINT),
                ("MINIO_ACCESS_KEY", settings.MINIO_ACCESS_KEY),
                ("MINIO_SECRET_KEY", settings.MINIO_SECRET_KEY),
                ("MINIO_BUCKET", settings.MINIO_BUCKET),
            )
            if not value
        ]
        if missing:
            return f"object storage is misconfigured: {', '.join(missing)} must be set"

        try:
            import boto3  # noqa: F401
        except ImportError:
            return (
                "object storage needs the boto3 package, which is not "
                "installed (pip install boto3)"
            )
        return None

    def external_url_warning(self) -> str | None:
        """Why a generated URL may not be reachable from the internet.

        Returned rather than raised: a deployment that only publishes to
        YouTube and X never needs an externally fetchable URL, so this is
        a caveat, not a failure.
        """
        if not self.enabled:
            return None
        if settings.MEDIA_PUBLIC_BASE_URL:
            if not settings.MEDIA_PUBLIC_BASE_URL.startswith("https://"):
                return (
                    "MEDIA_PUBLIC_BASE_URL is not HTTPS. Instagram and TikTok "
                    "both refuse plain HTTP media URLs."
                )
            return None

        host = urlparse(settings.MINIO_ENDPOINT or "").hostname or ""
        private = host in ("localhost", "127.0.0.1", "minio", "0.0.0.0", "")
        if private:
            return (
                f"MEDIA_PUBLIC_BASE_URL is not set, so media URLs are signed "
                f"against {settings.MINIO_ENDPOINT!r}. That address resolves "
                f"only inside this network, so Instagram and TikTok will not "
                f"be able to fetch the video. Set MEDIA_PUBLIC_BASE_URL to the "
                f"bucket's public HTTPS address."
            )
        return None

    def require_enabled(self) -> None:
        problem = self.configuration_error()
        if problem:
            raise StorageNotConfigured(problem.capitalize() + ".")

    # --- Clients -------------------------------------------------------------

    def _build_client(self, endpoint: str):
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                # SigV4 is what MinIO and every current S3 region expect;
                # botocore still defaults to SigV2 for some endpoints.
                signature_version="s3v4",
                s3={
                    "addressing_style": (
                        "path" if settings.S3_FORCE_PATH_STYLE else "auto"
                    )
                },
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    @property
    def client(self):
        """Client bound to the internal endpoint. Used for uploads."""
        self.require_enabled()
        with self._lock:
            if self._client is None:
                self._client = self._build_client(settings.MINIO_ENDPOINT)
            return self._client

    @property
    def public_client(self):
        """Client bound to the public endpoint. Used only for signing.

        A presigned URL's signature covers the host, so it has to be
        generated by a client pointed at the host the fetcher will use.
        Signing with the internal client and string-replacing the host
        afterwards invalidates the signature -- a tempting shortcut that
        produces 403s at the provider.
        """
        self.require_enabled()
        base = settings.MEDIA_PUBLIC_BASE_URL or settings.MINIO_ENDPOINT
        with self._lock:
            if self._public_client is None:
                self._public_client = self._build_client(base.rstrip("/"))
            return self._public_client

    def reset(self) -> None:
        """Drop cached clients. For tests that change settings."""
        with self._lock:
            self._client = None
            self._public_client = None
            self._bucket_checked = False

    # --- Bucket --------------------------------------------------------------

    def ensure_bucket(self) -> None:
        """Create the bucket if it is missing.

        Cheap to call repeatedly and done once per process, because a
        freshly provisioned MinIO has no buckets and the first upload would
        otherwise fail with NoSuchBucket.
        """
        if self._bucket_checked:
            return

        from botocore.exceptions import ClientError

        bucket = settings.MINIO_BUCKET
        try:
            self.client.head_bucket(Bucket=bucket)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in ("404", "NoSuchBucket", "NotFound"):
                raise StorageError(f"Cannot reach bucket {bucket!r}: {exc}") from exc
            try:
                self.client.create_bucket(Bucket=bucket)
                logger.info("created object storage bucket %r", bucket)
            except ClientError as create_exc:
                # Another worker may have won the race.
                if "BucketAlreadyOwnedByYou" not in str(create_exc):
                    raise StorageError(
                        f"Could not create bucket {bucket!r}: {create_exc}"
                    ) from create_exc

        self._bucket_checked = True

    # --- Operations ----------------------------------------------------------

    def upload(
        self,
        local_path: str | Path,
        key: str,
        content_type: str | None = None,
    ) -> StoredObject:
        """Put a local file in the bucket."""
        self.require_enabled()
        path = Path(local_path)
        if not path.is_file():
            raise StorageError(f"Cannot upload {path}: the file does not exist.")

        size = path.stat().st_size
        if size == 0:
            raise StorageError(f"Cannot upload {path}: the file is empty.")

        content_type = content_type or content_type_for(path)
        self.ensure_bucket()

        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self.client.upload_file(
                str(path),
                settings.MINIO_BUCKET,
                key,
                ExtraArgs={"ContentType": content_type},
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"Upload of {key!r} failed: {exc}") from exc

        return StoredObject(
            key=key,
            bucket=settings.MINIO_BUCKET,
            size_bytes=size,
            content_type=content_type,
            url=self.url_for(key),
        )

    def download(self, key: str, local_path: str | Path) -> Path:
        """Fetch an object back to local disk.

        Needed because YouTube and X upload bytes: if the scratch copy was
        cleaned up after the render, the worker has to retrieve it.
        """
        self.require_enabled()
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self.client.download_file(settings.MINIO_BUCKET, key, str(destination))
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"Download of {key!r} failed: {exc}") from exc
        return destination

    def exists(self, key: str) -> bool:
        self.require_enabled()
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=settings.MINIO_BUCKET, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self.require_enabled()
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self.client.delete_object(Bucket=settings.MINIO_BUCKET, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"Delete of {key!r} failed: {exc}") from exc

    def presigned_url(self, key: str, expires_in: int | None = None) -> str:
        """A time-limited URL for an object, signed against the public host."""
        self.require_enabled()
        expires_in = expires_in or settings.MEDIA_URL_EXPIRY_SECONDS

        from botocore.exceptions import BotoCoreError, ClientError

        try:
            return self.public_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.MINIO_BUCKET, "Key": key},
                ExpiresIn=expires_in,
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"Could not sign a URL for {key!r}: {exc}") from exc

    def url_for(self, key: str, expires_in: int | None = None) -> str:
        """The URL to hand a provider."""
        return self.presigned_url(key, expires_in=expires_in)


_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        _storage = ObjectStorage()
    return _storage


def reset_storage() -> None:
    """Drop the cached instance. Used by tests that change settings."""
    global _storage
    if _storage is not None:
        _storage.reset()
    _storage = None


# --- Resolution helpers -------------------------------------------------------
#
# Callers should not have to care whether a video lives on disk or in a
# bucket. These two functions answer the only questions publishing asks.


def is_object_key(value: str | None) -> bool:
    """Whether a stored pointer is a bucket key rather than a local path.

    Object keys are relative (``videos/3/7/x.mp4``); local paths from the
    renderer are absolute. Checking the shape avoids a schema migration and
    keeps rows written before object storage existed working unchanged.
    """
    if not value:
        return False
    return not os.path.isabs(value)


def local_copy(storage_key: str | None, work_dir: str | Path | None = None) -> Path | None:
    """A local file for a stored video, fetching it back if necessary.

    Returns None when no file can be produced, which the caller should
    treat as "not rendered yet" rather than an error.
    """
    if not storage_key:
        return None

    if not is_object_key(storage_key):
        path = Path(storage_key)
        return path if path.is_file() else None

    storage = get_storage()
    if storage.configuration_error():
        return None

    destination = Path(work_dir or settings.MEDIA_WORK_DIR) / "fetched" / Path(
        storage_key
    ).name
    if destination.is_file() and destination.stat().st_size > 0:
        return destination

    try:
        return storage.download(storage_key, destination)
    except StorageError as exc:
        logger.warning("Could not fetch %s from object storage: %s", storage_key, exc)
        return None


def public_url(storage_key: str | None, recorded: str | None = None) -> str | None:
    """A URL a provider can fetch, or None.

    ``recorded`` is any URL already stored on the video; an explicitly
    recorded URL wins, because it may point at a CDN this process knows
    nothing about.
    """
    if recorded:
        return recorded
    if not storage_key or not is_object_key(storage_key):
        return None

    storage = get_storage()
    if storage.configuration_error():
        return None

    try:
        return storage.url_for(storage_key)
    except StorageError as exc:
        logger.warning("Could not sign a URL for %s: %s", storage_key, exc)
        return None
