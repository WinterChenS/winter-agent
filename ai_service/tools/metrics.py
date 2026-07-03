from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolMetrics:
    """Per-tool invocation metrics.

    Attributes:
        invoke_count: Total number of invocations.
        total_latency_ms: Sum of all invocation latencies in milliseconds.
        error_count: Number of invocations that ended with an error.
    """

    invoke_count: int = 0
    total_latency_ms: int = 0
    error_count: int = 0
