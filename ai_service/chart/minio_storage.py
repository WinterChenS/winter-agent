"""MinIO image storage — upload generated charts and return public URLs."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class MinioStorage:
    """Upload images to MinIO and return presigned URLs."""

    def __init__(self, bucket: str = "agent-images") -> None:
        self._bucket = bucket

    def upload(self, filepath: str) -> str | None:
        """Upload file to MinIO. Returns presigned URL or None. Deletes local file on success."""
        try:
            from services.minio_client import upload_image
            url = upload_image(filepath, bucket=self._bucket)
            if url:
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                return url
            return None
        except Exception as e:
            logger.warning("MinioStorage upload failed: %s", e)
            return None
