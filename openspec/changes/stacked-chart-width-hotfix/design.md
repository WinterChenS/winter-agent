# stacked-chart-width-hotfix 设计

## 方案

采用最小修复，不扩展 `ChartSpec` API：

1. 强化 `ai_service/graph/nodes.py` 中 `_validate_chart_code_uses_spec_renderer()`
2. 显式拒绝 `ChartSpec(...)` 中出现 `width=` 或 `height=`
3. 拒绝理由明确指出应改用 `figsize=(12, 6)` 或直接省略该参数
4. 在提示词测试中补充对应回归，确保非法构造参数会在执行前被挡住

## 为什么这样修

- 报错来自生成代码不符合既有 `ChartSpec` 接口，而不是 `ChartSpec` 设计缺失
- 在校验层拦截可以避免运行时失败，并复用现有 chart-code retry 机制
- 不需要扩张 `ChartSpec` 的公共接口，也不会影响渲染器和 metadata 协议

## 非目标

- 不给 `ChartSpec` 新增 `width` / `height` 字段
- 不重构堆积图渲染逻辑
- 不修改 ChartSpec metadata 结构