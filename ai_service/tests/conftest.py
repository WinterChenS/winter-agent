from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest-asyncio to auto mode for async fixtures."""
    config.option.asyncio_mode = "auto"
