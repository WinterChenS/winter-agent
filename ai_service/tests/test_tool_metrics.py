from __future__ import annotations

from typing import Any, Mapping

import pytest

from tools.base import BaseTool, ToolResult
from tools.registry import ToolRegistry
from tools.schema import ToolSchema


class _EchoToolMetrics(BaseTool):
    name: str = "echo"
    description: str = "Echo"
    input_schema: dict[str, Any] = {"type": "object", "properties": {"msg": {"type": "string"}}}
    schema: ToolSchema = ToolSchema(parameters={"type": "object", "properties": {"msg": {"type": "string"}}})

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data=input_payload)


class TestToolMetrics:
    def test_metrics_start_empty(self):
        """新 registry 的 metrics 应为空。"""
        registry = ToolRegistry()
        assert registry.get_metrics("echo") is None

    def test_metrics_recorded_after_invoke(self):
        """调用工具后 metrics 应记录次数和耗时。"""
        registry = ToolRegistry()
        registry.register(_EchoToolMetrics())
        # Simulate what _execute_single_tool does
        registry.record_metric("echo", elapsed_ms=150, status="completed")
        metrics = registry.get_metrics("echo")
        assert metrics is not None
        assert metrics.invoke_count == 1
        assert metrics.total_latency_ms == 150
        assert metrics.error_count == 0

    def test_metrics_error_count(self):
        """错误调用应增加 error_count。"""
        registry = ToolRegistry()
        registry.register(_EchoToolMetrics())
        registry.record_metric("echo", elapsed_ms=50, status="error")
        metrics = registry.get_metrics("echo")
        assert metrics.error_count == 1

    def test_metrics_multiple_invocations(self):
        """多次调用应累积结果。"""
        registry = ToolRegistry()
        registry.register(_EchoToolMetrics())
        registry.record_metric("echo", elapsed_ms=100, status="completed")
        registry.record_metric("echo", elapsed_ms=200, status="completed")
        registry.record_metric("echo", elapsed_ms=50, status="error")
        metrics = registry.get_metrics("echo")
        assert metrics.invoke_count == 3
        assert metrics.total_latency_ms == 350
        assert metrics.error_count == 1


class TestToolLifecycleHooks:
    async def test_pre_hook_called_before_execution(self):
        """pre-hook 应在工具执行前被调用。"""
        registry = ToolRegistry()
        registry.register(_EchoToolMetrics())

        called_with: dict | None = {}

        async def pre_hook(name: str, inp: dict) -> dict | None:
            called_with["name"] = name
            called_with["inp"] = inp
            return inp

        registry.register_pre_hook(pre_hook)

        # Invoke to trigger hooks
        result = await registry.invoke("echo", {"msg": "hello"})
        assert result["ok"] is True
        assert called_with["name"] == "echo"
        assert called_with["inp"] == {"msg": "hello"}

    async def test_pre_hook_can_reject(self):
        """pre-hook 返回 None 应拒绝工具执行。"""
        registry = ToolRegistry()
        registry.register(_EchoToolMetrics())

        async def rejecting_hook(name: str, inp: dict) -> dict | None:
            return None  # reject

        registry.register_pre_hook(rejecting_hook)
        result = await registry.invoke("echo", {"msg": "hello"})
        assert result["ok"] is False

    async def test_post_hook_called_after_execution(self):
        """post-hook 应在工具执行后被调用。"""
        registry = ToolRegistry()
        registry.register(_EchoToolMetrics())

        post_called: dict | None = {}

        async def post_hook(name: str, inp: dict, res: dict) -> None:
            post_called["name"] = name
            post_called["inp"] = inp
            post_called["res"] = res

        registry.register_post_hook(post_hook)
        result = await registry.invoke("echo", {"msg": "world"})
        assert result["ok"] is True
        assert post_called["name"] == "echo"
        assert post_called["inp"] == {"msg": "world"}
        assert post_called["res"]["ok"] is True

    async def test_multiple_pre_hooks_chain(self):
        """多个 pre-hook 应按注册顺序链式调用。"""
        registry = ToolRegistry()
        registry.register(_EchoToolMetrics())
        order: list[str] = []

        async def hook_a(name: str, inp: dict) -> dict | None:
            order.append("a")
            return inp

        async def hook_b(name: str, inp: dict) -> dict | None:
            order.append("b")
            return inp

        registry.register_pre_hook(hook_a)
        registry.register_pre_hook(hook_b)
        await registry.invoke("echo", {"msg": "test"})
        assert order == ["a", "b"]

    async def test_multiple_post_hooks_chain(self):
        """多个 post-hook 应按注册顺序链式调用。"""
        registry = ToolRegistry()
        registry.register(_EchoToolMetrics())
        order: list[str] = []

        async def hook_a(name: str, inp: dict, res: dict) -> None:
            order.append("a")

        async def hook_b(name: str, inp: dict, res: dict) -> None:
            order.append("b")

        registry.register_post_hook(hook_a)
        registry.register_post_hook(hook_b)
        await registry.invoke("echo", {"msg": "test"})
        assert order == ["a", "b"]
