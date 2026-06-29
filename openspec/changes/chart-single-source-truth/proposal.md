## Why

Data Analyst Agent 生成的图表与 Markdown 分析经常不一致——颜色、数值、趋势描述错误。根本原因是 LLM 根据图片进行视觉推理而不是引用真实数据，属于典型 Hallucination。chart-infrastructure-v2 建立了 Palette、ChartResult、FontManager 等基础设施的 spec，但采用"从 matplotlib figure state 反向提取 metadata"的方案，metadata 准确性依赖 LLM 生成的代码是否规范设置了 matplotlib 属性。本次采用 ChartSpec 先行方案，从源头保证 metadata 与图片完全一致。

## What Changes

- **新增 ChartSpec 数据结构**：类型特定字段（bar/line 用 series，pie 用 slices，scatter 用 points），LLM 代码必须先构建 ChartSpec 再渲染
- **重构 ChartRenderer**：新增 `render_from_spec(chart_spec)` 方法，从 ChartSpec 渲染图表并自动提取 metadata；保留 `render(code, output_path)` 向后兼容
- **新增 Palette 固定调色板**：PRIMARY/SECONDARY/SUCCESS/WARNING/ERROR + 扩展序列色，每个颜色含 hex 值和中文 colorName
- **新增 FontManager**：统一字体管理，FontProperties 缓存，替代 rcParams 方案
- **增强 ChartResult**：image_path + metadata（从 ChartSpec 派生）+ summary（ChartRenderer 自动计算 max/min/avg/trend）
- **更新 execute_python 返回格式**：ToolResult 中增加 metadata 字段
- **更新 Prompt**：chart code prompt 要求使用 ChartSpec API；composer prompt 要求引用 metadata 而非推测；Data Analyst system prompt 增加 metadata 引用规则
- **ChartRenderer 自动计算 summary**：从 ChartSpec.values 提取 max/min/avg/trend，无需 LLM 编写

## Capabilities

### New Capabilities

- `chart-spec`: ChartSpec 数据结构，类型特定字段，作为图表渲染和 metadata 的 Single Source of Truth

### Modified Capabilities

- `chart-palette`: Palette 增加 PRIMARY/SECONDARY/SUCCESS/WARNING/ERROR 常量，每个 PaletteColor 含 hex + name_cn
- `chart-font-management`: 新增 FontManager 类，跨平台字体发现与 FontProperties 缓存
- `chart-rendering`: ChartRenderer 新增 `render_from_spec(ChartSpec)` 方法，从 ChartSpec 渲染并返回 ChartResult；旧 `render(code,path)` 保持兼容
- `chart-result-metadata`: ChartResult.metadata 直接由 ChartSpec 派生，summary 由 ChartRenderer 自动计算
- `chart-markdown-composition`: Composer prompt 增加 metadata 引用规则，禁止推测颜色/数值

## Impact

- `ai_service/chart/` — 新增 chart_spec.py, palette.py, font_manager.py；重构 matplotlib_renderer.py
- `ai_service/tools/sandbox/tool.py` — preamble 注入 FontManager、Palette、ChartSpec 导入；ToolResult 增加 metadata
- `ai_service/graph/nodes.py` — _CHART_CODE_PROMPT 改用 ChartSpec API；_build_composer_system_prompt 增加 metadata 引用规则
- `ai_service/db/migrations/002_seed_agents_and_setup.sql` — Data Analyst Agent system prompt 增加 metadata 引用规则
