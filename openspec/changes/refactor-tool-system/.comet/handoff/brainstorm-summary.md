# Brainstorm Summary

- Change: refactor-tool-system
- Date: 2026-06-25

## 确认的技术方案

1. **@tool 装饰器 + Registry 启动扫描**：`@tool` 装饰器在类上存元数据 `_is_tool=True`，`ToolRegistry` 启动时扫描 `BaseTool.__subclasses__()` 自动发现并注册
2. **并行工具允许混合类型**：`search` + `browser` + `time` 可混合并行，代码层面不限制类型
3. **代码沙箱用 Pyodide WASM**：纯 Python，Docker 兼容，无需特权模式，预装 pandas/numpy/matplotlib

## 关键取舍与风险

- 放弃了 Docker 沙箱的完全隔离 + 自由 pip 安装，换取了 Docker-in-Docker 兼容 + 低延迟
- 并行执行限制最多 3 个工具，避免 token 消耗爆炸
- 保持 JSON Mode（非 Function Calling），用更强的 prompt 保证格式
- 向后兼容单工具协议

## 测试策略

- `ToolSchema` 校验单元测试
- `ToolRegistry` 自动发现 mock 文件系统扫描测试
- 并行执行 success/error/mixed 单元测试
- Pyodide sandbox 集成测试（代码执行、超时、错误处理）
- 端到端：启动自动发现 → 并行搜索 → sandbox 执行 → 结果流式

## Spec Patch

无
