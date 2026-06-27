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
