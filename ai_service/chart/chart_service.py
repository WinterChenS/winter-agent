"""ChartService — unified entry point for chart generation.

Only this module should be imported by tools/agents. Internal renderer/storage
details are hidden behind this facade, allowing engine swaps without changes
to callers or prompts.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from chart.minio_storage import MinioStorage
from chart.renderers.matplotlib_renderer import MatplotlibRenderer

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp")


class ChartService:
    """Generate charts from Python code, upload to MinIO, return structured dict."""

    def __init__(self):
        self._renderer = MatplotlibRenderer()
        self._storage = MinioStorage()

    def render(self, code: str) -> dict:
        """Execute matplotlib code and return structured dict with metadata.

        The code is executed with FontManager + cn_font + Palette injected.
        If __chart_spec__ is declared, the renderer uses render_from_spec
        internally and returns full metadata.

        Returns:
            On success::
                {
                    "type": "image",
                    "url": "https://minio/chart_abc.png",
                    "metadata": {"title": "...", "chart_type": "...", ...},
                    "metadata_url": "https://minio/chart_abc_metadata.json",
                    "summary": "...",
                }
            On error::
                {"type": "error", "error": "Chart rendering failed: ..."}
        """
        filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        output_path = str(OUTPUT_DIR / filename)

        try:
            result = self._renderer.render(code, output_path)
        except Exception as e:
            logger.exception("Chart rendering failed")
            return {"type": "error", "error": f"Chart rendering failed: {e}"}

        # Upload PNG
        url = self._storage.upload(output_path)
        if not url:
            url = f"file://{output_path}"

        # Upload metadata.json if present
        metadata_url = None
        json_path = output_path.replace(".png", "_metadata.json")
        if os.path.isfile(json_path):
            metadata_url = self._storage.upload(json_path)

        return {
            "type": "image",
            "url": url,
            "metadata": result.metadata,
            "metadata_url": metadata_url,
            "summary": result.summary,
        }
