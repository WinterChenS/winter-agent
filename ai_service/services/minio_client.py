"""MinIO client for uploading generated images (charts, screenshots, etc.)."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import timedelta
from pathlib import Path

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

# Workspace root where execute_python saves images
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def _get_client() -> Minio | None:
    """Build MinIO client from environment variables. Returns None if not configured."""
    endpoint = os.getenv("MINIO_ENDPOINT", "")
    access_key = os.getenv("MINIO_ACCESS_KEY", "")
    secret_key = os.getenv("MINIO_SECRET_KEY", "")
    if not all([endpoint, access_key, secret_key]):
        logger.warning("MinIO not configured, skipping image upload")
        return None

    # Strip https:// prefix for Minio client
    host = endpoint.replace("https://", "").replace("http://", "")
    secure = endpoint.startswith("https://")

    return Minio(
        host,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
        cert_check=False,  # Self-signed certs in dev
    )


def _ensure_bucket(client: Minio, bucket: str = "agent-images") -> bool:
    """Create bucket if it doesn't exist."""
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        return True
    except S3Error as e:
        logger.error("Failed to ensure bucket %s: %s", bucket, e)
        return False


def upload_image(filepath: str, bucket: str = "agent-images") -> str | None:
    """Upload an image file to MinIO. Returns the public URL or None on failure."""
    client = _get_client()
    if not client:
        return None

    if not _ensure_bucket(client, bucket):
        return None

    path = Path(filepath)
    if not path.is_absolute():
        # Try relative to workspace root
        path = WORKSPACE_ROOT / filepath

    if not path.exists():
        logger.warning("Image file not found: %s", path)
        return None

    # Generate unique object name
    ext = path.suffix or ".png"
    object_name = f"{uuid.uuid4().hex}{ext}"

    try:
        client.fput_object(
            bucket_name=bucket,
            object_name=object_name,
            file_path=str(path),
            content_type=f"image/{ext.lstrip('.')}",
        )

        # Generate a presigned URL valid for 7 days
        url = client.presigned_get_object(
            bucket_name=bucket,
            object_name=object_name,
            expires=timedelta(days=7),
        )

        logger.info("Uploaded %s → MinIO %s/%s", path.name, bucket, object_name)
        return url

    except S3Error as e:
        logger.error("MinIO upload failed for %s: %s", path, e)
        return None


def scan_and_upload_images(output_text: str) -> dict[str, str]:
    """Scan tool output for saved image files, upload them to MinIO.
    Returns dict of {filename: minio_url}."""
    uploaded: dict[str, str] = {}

    client = _get_client()
    if not client:
        return uploaded

    # Look for patterns like "✅ 图1已保存: stock_trends.png" or ".png" files
    import re
    # Match common image file references in output
    patterns = [
        r'已保存[：:]\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r'saved[：:]\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r'保存[到至][：:]\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r'→\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r'=>\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
    ]

    found_files = set()
    for pattern in patterns:
        for match in re.finditer(pattern, output_text, re.IGNORECASE):
            found_files.add(match.group(1))

    # Also scan workspace root for recently created .png files
    try:
        for p in WORKSPACE_ROOT.glob("*.png"):
            if p.name not in found_files:
                # Check if this file was created in the last 60 seconds
                mtime = p.stat().st_mtime
                if (__import__("time").time() - mtime) < 60:
                    found_files.add(p.name)
    except Exception:
        pass

    for filename in found_files:
        url = upload_image(str(WORKSPACE_ROOT / filename))
        if url:
            uploaded[filename] = url

    return uploaded
