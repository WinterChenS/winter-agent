from __future__ import annotations

import pytest

from tools.base import ToolResult
from tools.sandbox.tool import CodeSandboxTool


@pytest.fixture
def sandbox() -> CodeSandboxTool:
    return CodeSandboxTool()


class TestCodeSandbox:
    """Tests for CodeSandboxTool — subprocess-based Python code execution."""

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, sandbox: CodeSandboxTool) -> None:
        """执行简单 print 应返回 stdout 输出。"""
        result: ToolResult = await sandbox.execute({"code": 'print("hello")'})
        assert result.ok is True
        assert "hello" in result.data.get("output", "")

    @pytest.mark.asyncio
    async def test_execute_computation(self, sandbox: CodeSandboxTool) -> None:
        """执行数值计算应返回正确结果。"""
        result: ToolResult = await sandbox.execute({"code": "print(2 + 2)"})
        assert result.ok is True
        assert "4" in result.data.get("output", "")

    @pytest.mark.asyncio
    async def test_import_pandas_and_use_it(self, sandbox: CodeSandboxTool) -> None:
        """应能导入 pandas 并执行简单操作。"""
        code = """
import pandas as pd
df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
print(df.shape)
"""
        result: ToolResult = await sandbox.execute({"code": code})
        assert result.ok is True
        output = result.data.get("output", "")
        # df.shape prints "(2, 2)"
        assert "(2, 2)" in output

    @pytest.mark.asyncio
    async def test_import_scipy_and_use_it(self, sandbox: CodeSandboxTool) -> None:
        """应能导入 scipy 并访问版本信息。"""
        code = """
import scipy
print(scipy.__version__)
"""
        result: ToolResult = await sandbox.execute({"code": code})
        assert result.ok is True
        output = result.data.get("output", "")
        assert output.strip()

    @pytest.mark.asyncio
    async def test_timeout_kills_long_running_code(self, sandbox: CodeSandboxTool) -> None:
        """无限循环应在超时后返回 TIMEOUT 错误。"""
        result: ToolResult = await sandbox.execute({"code": "while True: pass", "timeout": 2})
        assert result.ok is False
        assert result.error is not None
        assert "TIMEOUT" in result.error.code.upper() or "timeout" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_error_handling(self, sandbox: CodeSandboxTool) -> None:
        """执行异常代码应返回错误信息。"""
        result: ToolResult = await sandbox.execute({"code": "1/0"})
        assert result.ok is False
        assert result.error is not None
        assert "ZeroDivisionError" in result.error.message or "division by zero" in result.error.message.lower()

    # ──────────────────────────────────────────────
    # Task 7 tests: preamble + charts in result
    # ──────────────────────────────────────────────

    def test_preamble_includes_chart_imports(self, sandbox: CodeSandboxTool) -> None:
        """_build_preamble() 应注入 FontManager/Palette/ChartSpec/MatplotlibRenderer 导入。"""
        preamble = sandbox._build_preamble()
        assert "from chart.font_manager import FontManager" in preamble
        assert "cn_font = FontManager.get_cn_font()" in preamble
        assert "from chart.palette import Palette" in preamble
        assert "from chart.chart_spec import ChartSpec, SeriesSpec, SliceSpec, PointSpec" in preamble
        assert "from chart.renderers.matplotlib_renderer import MatplotlibRenderer" in preamble

    @pytest.mark.asyncio
    async def test_execute_returns_charts_key(self, sandbox: CodeSandboxTool) -> None:
        """execute() 返回的 data 应包含 charts 键。"""
        result: ToolResult = await sandbox.execute({"code": 'print("no charts")'})
        assert result.ok is True
        assert "charts" in result.data
        assert isinstance(result.data["charts"], list)
        assert len(result.data["charts"]) == 0

    # ── execute_stream tests ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_execute_stream_basic(self, sandbox: CodeSandboxTool) -> None:
        """execute_stream 应产生与 execute 相同的结果。"""
        from core.streaming_event_bus import StreamingEventBus

        bus = StreamingEventBus()
        result = await sandbox.execute_stream({"code": 'print("hello stream")'}, bus)
        assert result.ok is True
        assert "hello stream" in result.data.get("output", "")

    @pytest.mark.asyncio
    async def test_execute_stream_emits_start_and_completed(self, sandbox: CodeSandboxTool) -> None:
        """execute_stream 应发出 tool.started 和 tool.completed 事件。"""
        from core.streaming_event_bus import StreamingEventBus

        bus = StreamingEventBus()
        events: list[tuple[str, dict]] = []

        original_emit = bus.emit
        def capture_emit(event_type: str, **data: object) -> None:
            events.append((event_type, data))
            original_emit(event_type, **data)
        bus.emit = capture_emit

        result = await sandbox.execute_stream({"code": 'print("done")'}, bus)
        assert result.ok is True

        event_types = [e[0] for e in events]
        assert "tool.started" in event_types
        assert "tool.completed" in event_types

    @pytest.mark.asyncio
    async def test_execute_stream_error(self, sandbox: CodeSandboxTool) -> None:
        """execute_stream 应正确处理执行错误。"""
        from core.streaming_event_bus import StreamingEventBus

        bus = StreamingEventBus()
        result = await sandbox.execute_stream({"code": "1/0"}, bus)
        assert result.ok is False
        assert result.error is not None
