from __future__ import annotations

import logging
from typing import Any, Mapping

from tools.base import BaseTool, ToolResult
from tools.schema import tool, ToolSchema

logger = logging.getLogger(__name__)


@tool
class TimeTool(BaseTool):
    name = "time"
    description = "Get the current date and time. Useful for questions about the current time or date."
    input_schema = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "The timezone to get the time for (e.g., 'Asia/Shanghai', 'UTC'). Defaults to local system time if not provided."
            }
        },
        "required": [],
    }
    schema: ToolSchema = ToolSchema(
        parameters={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "The timezone to get the time for (e.g., 'Asia/Shanghai', 'UTC'). Defaults to local system time if not provided."
                }
            },
            "required": [],
        },
    )

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        try:
            from datetime import datetime
            import pytz  # 建议安装 pytz 库以支持标准时区处理 (pip install pytz)

            # 1. 提取并校验输入参数
            timezone_str = input_payload.get("timezone")
            logger.info(f"Received time tool request with timezone: {timezone_str}")
            if timezone_str:
                # 如果传入了时区参数，尝试解析
                try:
                    tz = pytz.timezone(str(timezone_str))
                    current_time = datetime.now(tz)
                    # 格式化输出带时区的时间，例如：2026-05-19 22:11:15 CST+0800
                    time_str = current_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')
                except Exception:
                    # 如果传入的时区不合法，记录警告并回退到本地时间
                    logger.warning(f"Unknown timezone '{timezone_str}', falling back to local time.")
                    current_time = datetime.now()
                    time_str = f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} (Warning: Unknown timezone '{timezone_str}')"
            else:
                # 2. 未传时区，直接获取系统本地时间
                current_time = datetime.now()
                time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

            logger.info(f"Successfully retrieved current time: {time_str}")
            # 3. 按照 SearchTool 的规范，返回成功的 ToolResult
            return ToolResult.success(time_str)

        except Exception as exc:
            # 4. 捕获其他未知异常，按照规范返回失败的 ToolResult
            logger.exception(f"Time tool execution failed")
            return ToolResult.failure(
                code="TOOL_EXECUTION_ERROR",
                message=f"time tool execution failed: {str(exc)}",
                retryable=True,
            )