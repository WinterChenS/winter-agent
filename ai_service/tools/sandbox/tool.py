from __future__ import annotations

import asyncio
import logging
import platform
import sys
from typing import Any, Mapping

from tools.base import BaseTool, ToolResult
from tools.schema import tool, ToolSchema

logger = logging.getLogger(__name__)


@tool
class CodeSandboxTool(BaseTool):
    """Execute Python code using subprocess for data analysis and computation.

    Each invocation spawns a fresh subprocess running the given Python code
    with a configurable timeout (default 30 s).  stdout and stderr are
    captured separately.  On Linux the subprocess also has its memory capped
    at 256 MB via ``resource.setrlimit``.

    Note: runs with the same privileges as the AI service process.
    Pre-installed packages (pandas, numpy, matplotlib) are available
    automatically.
    """

    name = "execute_python"
    description = (
        "Execute Python code using subprocess for data analysis and computation. "
        "Note: runs with the same privileges as the AI service process."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds (default 30, max 60)",
                "default": 30,
            },
        },
        "required": ["code"],
    }
    schema: ToolSchema = ToolSchema(
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds (default 30, max 60)",
                    "default": 30,
                },
            },
            "required": ["code"],
        },
    )

    # ------------------------------------------------------------------
    # Resource limits (Linux only)
    # ------------------------------------------------------------------
    _MAX_MEMORY_BYTES = 256 * 1024 * 1024  # 256 MB

    @staticmethod
    def _build_preamble() -> str:
        """Return code that initializes chart theme and sets resource limits on Linux."""
        import os as _os
        lines = []

        # ── Ensure ai_service is on path for chart module imports ──
        ai_service_dir = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        lines.append(f"import sys; sys.path.insert(0, {ai_service_dir!r})")
        lines.append("")

        # ── Chart theme (font, DPI, style) ──
        lines.append("from chart.chart_theme import ChartTheme")
        lines.append("ChartTheme.initialize()")
        lines.append("")

        # ── Linux resource limits ──
        if platform.system() == "Linux":
            lines.append("import resource")
            lines.append(f"resource.setrlimit(resource.RLIMIT_AS, ({CodeSandboxTool._MAX_MEMORY_BYTES}, {CodeSandboxTool._MAX_MEMORY_BYTES}))")

        return "\n".join(lines) + "\n"

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        code: str = str(input_payload.get("code", "")).strip()
        if not code:
            return ToolResult.failure(
                code="INVALID_INPUT",
                message="code is required and must be a non-empty string",
                retryable=False,
            )

        timeout: int = int(input_payload.get("timeout", 30))
        timeout = min(max(timeout, 1), 60)  # clamp 1..60

        # Prepend resource-limit preamble on Linux
        preamble = self._build_preamble()
        full_code = f"{preamble}\n{code}" if preamble else code

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                full_code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                # Subprocess failed — return error details
                message = stderr_str.strip() or stdout_str.strip() or f"Process exited with code {proc.returncode}"
                return ToolResult.failure(
                    code="EXECUTION_ERROR",
                    message=message[:500],
                    retryable=False,
                )

            output = stdout_str
            if stderr_str:
                output += "\n[stderr]\n" + stderr_str

            # Scan for generated image files and upload to MinIO
            import re as _re
            import os as _os_module
            png_patterns = [
                _r'已(?:生成[并且]?)?保存[为至]?\s*[：:]?\s*(\S+\.(?:png|jpg|jpeg|gif|svg))',
                _r'savefig\(["\']([^"\']+\.(?:png|jpg|jpeg|gif|svg))',
                _r'(\S+\.png)',
            ]
            uploaded: dict[str, str] = {}
            cwd = _os_module.getcwd()
            for pat in png_patterns:
                for m in _re.finditer(pat, output):
                    fname = m.group(1)
                    fpath = _os_module.path.join(cwd, fname)
                    if _os_module.path.isfile(fpath) and fname not in uploaded:
                        try:
                            from services.minio_client import upload_image
                            url = upload_image(fpath)
                            if url:
                                uploaded[fname] = url
                        except Exception:
                            pass

            # Also scan CWD for any new PNGs created during execution
            import time as _time
            now = _time.time()
            for f in _os_module.listdir(cwd):
                if f.endswith('.png') and f not in uploaded:
                    fpath = _os_module.path.join(cwd, f)
                    try:
                        if _os_module.path.getmtime(fpath) > now - 120:
                            url = upload_image(fpath)
                            if url:
                                uploaded[f] = url
                    except Exception:
                        pass

            if uploaded:
                urls_text = "\n".join(f"{fn} → {url}" for fn, url in uploaded.items())
                output = f"{output}\n\n[图片已上传]\n{urls_text}"

            return ToolResult.success({
                "output": output.strip() or "(no output)",
                "images": uploaded,
            })

        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                logger.warning("Failed to kill timed-out subprocess", exc_info=True)
            return ToolResult.failure(
                code="TIMEOUT",
                message=f"Code execution exceeded {timeout}s limit",
                retryable=False,
            )
        except Exception as exc:
            return ToolResult.failure(
                code="EXECUTION_ERROR",
                message=str(exc)[:200],
                retryable=False,
            )
