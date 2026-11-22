"""Storage Service for MinIO/S3."""

import os
from datetime import timedelta
from typing import Optional
from minio import Minio
from minio.error import S3Error

from app.config import get_settings

settings = get_settings()

# Initialize MinIO client
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
    region="us-east-1",
)

# Separate client for presigning URLs, so links point at an address the
# browser can actually reach instead of the internal docker hostname.
minio_public_client = Minio(
    settings.minio_public_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
    region="us-east-1",
)


def ensure_bucket() -> None:
    """Create the configured bucket if it does not exist yet."""
    if not minio_client.bucket_exists(settings.minio_bucket):
        minio_client.make_bucket(settings.minio_bucket)


async def upload_file(file, prefix: str = "") -> str:
    """Upload a file to MinIO and return storage key."""
    import uuid

    # Generate unique key
    ext = os.path.splitext(file.filename or "")[1]
    key = f"{prefix}/{uuid.uuid4().hex}{ext}"

    # Read file content
    content = await file.read()

    # Upload to MinIO
    minio_client.put_object(
        settings.minio_bucket,
        key,
        content,
        len(content),
        content_type=file.content_type or "application/octet-stream",
    )

    return key


async def delete_file(storage_key: str) -> bool:
    """Delete a file from MinIO."""
    try:
        minio_client.remove_object(settings.minio_bucket, storage_key)
        return True
    except S3Error:
        return False


def get_file_url(storage_key: str) -> str:
    """Get a presigned URL for a file."""
    try:
        url = minio_public_client.presigned_get_object(
            settings.minio_bucket,
            storage_key,
            expires=timedelta(hours=1),
        )
        return url
    except S3Error:
        return ""


def file_exists(storage_key: str) -> bool:
    """Check whether an object exists in the bucket."""
    try:
        minio_client.stat_object(settings.minio_bucket, storage_key)
        return True
    except S3Error:
        return False


async def get_file_content(storage_key: str) -> bytes:
    """Get file content from MinIO."""
    try:
        response = minio_client.get_object(settings.minio_bucket, storage_key)
        return response.read()
    except S3Error:
        return b""


async def list_files(prefix: str = "") -> list:
    """List files in MinIO with given prefix."""
    try:
        objects = minio_client.list_objects(settings.minio_bucket, prefix=prefix)
        return [obj.object_name for obj in objects]
    except S3Error:
        return []