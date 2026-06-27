"""MinIO client for uploading generated images (charts, screenshots, etc.)."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import timedelta
from pathlib import Path

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

# AI service root where execute_python saves images (ai_service/)
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
# Also check parent project root for images saved from different CWDs
PROJECT_ROOT = WORKSPACE_ROOT.parent


def _get_client() -> Minio | None:
    """Build MinIO client from environment variables. Returns None if not configured."""
    # Ensure .env is loaded (may not be loaded in subprocess contexts)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    endpoint = os.getenv("MINIO_ENDPOINT", "")
    access_key = os.getenv("MINIO_ACCESS_KEY", "")
    secret_key = os.getenv("MINIO_SECRET_KEY", "")
    if not all([endpoint, access_key, secret_key]):
        logger.warning("MinIO not configured, skipping image upload (endpoint=%s, key=%s)",
                       bool(endpoint), bool(access_key))
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
        r'已(?:生成[并且]?)?保存[为至]?[：:]\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r'saved?\s*(?:as|to)?[：:]\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r'图表已.*?(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r'→\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r'=>\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
        r"savefig\(['\"]([^'\"]+\.(?:png|jpg|jpeg|gif|svg))",
        r"\.savefig\(['\"]([^'\"]+\.(?:png|jpg|jpeg|gif|svg))",
        r'(\S+\.png)',  # Any .png filename as fallback
    ]

    found_files = set()
    for pattern in patterns:
        for match in re.finditer(pattern, output_text, re.IGNORECASE):
            found_files.add(match.group(1))

    # Also scan for recently created .png files (regardless of output text)
    try:
        import time as _time
        now = _time.time()
        for root_dir in (WORKSPACE_ROOT, PROJECT_ROOT):
            for p in root_dir.glob("*.png"):
                fp = str(p)
                if fp not in found_files:
                    mtime = p.stat().st_mtime
                    if (now - mtime) < 300:  # 5 min window
                        found_files.add(fp)
                        logger.info("Found recent PNG: %s (age=%ds)", p.name, int(now - mtime))
    except Exception:
        pass

    for filepath in found_files:
        url = upload_image(filepath)
        if url:
            uploaded[Path(filepath).name] = url

    return uploaded
