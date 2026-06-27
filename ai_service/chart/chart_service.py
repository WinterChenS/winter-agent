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
    """Generate charts from Python code, upload to MinIO, return image URL dict."""

    def __init__(self):
        self._renderer = MatplotlibRenderer()
        self._storage = MinioStorage()

    def render(self, code: str) -> dict:
        """Execute matplotlib code and return {"type": "image", "url": "...", ...}.

        The code is executed with ChartTheme applied. If the code calls
        plt.savefig(), that file is used; otherwise a figure is auto-saved.
        """
        filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        output_path = str(OUTPUT_DIR / filename)

        try:
            self._renderer.render(code, output_path)
        except Exception as e:
            logger.exception("Chart rendering failed")
            return {"type": "error", "error": f"Chart rendering failed: {e}"}

        url = self._storage.upload(output_path)
        if not url:
            # Fallback: return local path info
            return {
                "type": "image",
                "url": f"file://{output_path}",
                "width": 1600,
                "height": 900,
                "title": filename,
            }

        return {
            "type": "image",
            "url": url,
            "width": 1600,
            "height": 900,
            "title": filename,
        }
