"""Tests for ChartService — metadata, summary, and metadata.json upload."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from chart.chart_result import ChartResult
from chart.chart_service import ChartService


@pytest.fixture
def chart_result() -> ChartResult:
    return ChartResult(
        image_path="/tmp/chart_test.png",
        metadata={"title": "Sales", "chart_type": "bar", "figsize": [12, 6]},
        summary="Max: 200 | Min: 100 | Avg: 150 | trend: ↑ | growth: +100.0%",
        stdout="",
    )


@pytest.fixture
def chart_service() -> ChartService:
    return ChartService()


class TestChartServiceRender:
    """Tests for ChartService.render() behavior."""

    def test_render_success_returns_image_type(
        self, chart_service: ChartService
    ) -> None:
        """render() returns dict with type='image' on success."""
        result = chart_service.render("import matplotlib.pyplot as plt")
        assert isinstance(result, dict)
        assert result["type"] == "image"

    def test_render_success_has_url_key(
        self, chart_service: ChartService
    ) -> None:
        """render() returns a dict with 'url' key on success."""
        result = chart_service.render("import matplotlib.pyplot as plt")
        assert "url" in result
        assert isinstance(result["url"], str)

    def test_render_returns_metadata_from_chart_result(
        self, chart_service: ChartService
    ) -> None:
        """render() includes metadata from ChartResult in the return dict."""
        result = chart_service.render("import matplotlib.pyplot as plt")
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)

    def test_render_returns_summary_from_chart_result(
        self, chart_service: ChartService
    ) -> None:
        """render() includes summary from ChartResult in the return dict."""
        result = chart_service.render("import matplotlib.pyplot as plt")
        assert "summary" in result
        assert isinstance(result["summary"], str)

    def test_render_error_returns_error_type(
        self, chart_service: ChartService
    ) -> None:
        """render() returns dict with type='error' on failure."""
        with patch.object(
            chart_service._renderer, "render", side_effect=RuntimeError("boom")
        ):
            result = chart_service.render("bad code")

        assert result["type"] == "error"
        assert "error" in result

    def test_render_png_uploaded_to_storage(
        self, chart_service: ChartService
    ) -> None:
        """render() uploads the generated PNG via storage."""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "https://minio/test.png"
        chart_service._storage = mock_storage

        chart_service.render("import matplotlib.pyplot as plt")

        mock_storage.upload.assert_called()
        uploaded_path = mock_storage.upload.call_args[0][0]
        assert uploaded_path.endswith(".png"), f"Expected .png, got {uploaded_path}"

    def test_render_metadata_json_uploaded_when_exists(
        self, chart_service: ChartService
    ) -> None:
        """render() uploads _metadata.json if it exists beside the PNG."""
        mock_storage = MagicMock()
        mock_storage.upload.side_effect = lambda p: (
            f"https://minio/{os.path.basename(p)}"
        )
        chart_service._storage = mock_storage

        fixed_hex = "a1b2c3d4"
        output_path = f"/tmp/chart_{fixed_hex}.png"
        json_path = output_path.replace(".png", "_metadata.json")
        json_url = f"https://minio/chart_{fixed_hex}_metadata.json"

        with patch.object(chart_service, "_renderer") as mock_renderer, \
             patch("chart.chart_service.uuid.uuid4") as mock_uuid:
            mock_uuid_obj = MagicMock()
            mock_uuid_obj.hex = fixed_hex
            mock_uuid.return_value = mock_uuid_obj

            mock_renderer.render.return_value = ChartResult(
                image_path=output_path,
                metadata={"title": "Test"},
                summary="test",
                stdout="",
            )
            # Side effect for upload: return specific URL for metadata json
            def _upload_side_effect(p):
                if "metadata" in p:
                    return json_url
                return f"https://minio/chart_{fixed_hex}.png"
            mock_storage.upload.side_effect = _upload_side_effect

            # Create a fake metadata.json
            try:
                with open(json_path, "w") as f:
                    json.dump({"title": "Test"}, f)

                result = chart_service.render("code")

                assert result["metadata_url"] == json_url
                assert "_metadata.json" in result["metadata_url"]
            finally:
                if os.path.isfile(json_path):
                    os.remove(json_path)

    def test_render_local_url_when_upload_fails(
        self, chart_service: ChartService
    ) -> None:
        """render() falls back to file:// URL when storage upload returns None."""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = None
        chart_service._storage = mock_storage

        result = chart_service.render("import matplotlib.pyplot as plt")

        assert result["url"].startswith("file://")

    def test_render_metadata_url_is_none_without_json(
        self, chart_service: ChartService
    ) -> None:
        """render() sets metadata_url to None when no _metadata.json exists."""
        # By default, the renderer does not produce a _metadata.json for raw code
        result = chart_service.render("import matplotlib.pyplot as plt; print('no spec')")
        assert result["metadata_url"] is None

    def test_render_returns_error_on_renderer_failure(
        self, chart_service: ChartService
    ) -> None:
        """render() returns error dict when renderer raises an exception."""
        with patch.object(
            chart_service._renderer, "render", side_effect=ValueError("invalid")
        ):
            result = chart_service.render("bad")

        assert result["type"] == "error"
        assert "invalid" in result["error"]
