## Why

Data Analyst Agent 的图表生成存在三个系统性缺陷：LLM 凭记忆描述颜色导致图文不一致（Hallucination）、matplotlib Artist 层中文乱码（rcParams 不能覆盖所有文本元素）、颜色随机无企业级调色板。这些问题不能通过修改 Prompt 解决，需要从图表生成流程、字体管理、元数据输出三个层面彻底重构基础设施。

## What Changes

- **新增 FontManager**：统一字体管理，启动时缓存 FontProperties，所有 matplotlib Artist（title/xlabel/ylabel/legend/annotate/text/table cells/colorbar labels/tick labels/suptitle）强制使用 `fontproperties=` 参数
- **新增 Palette 企业调色板**：PRIMARY/SECONDARY/SUCCESS/WARNING/ERROR + 扩展序列色，每个颜色含 `color_name` 中文映射
- **新增 ChartResult 数据结构**：统一图表结果 `image_path + metadata + summary`，取代当前只返回 URL/路径
- **重构 ChartRenderer**：`render()` 返回 ChartResult，封装 matplotlib 渲染逻辑
- **新增 Metadata 输出**：每张图同时输出 `chart_metadata.json`，与 PNG 同目录同名
- **重构 Markdown 生成**：composer/answer 阶段引用 ChartResult.metadata 和 summary，禁止 LLM 自行描述颜色
- **优化所有相关 Prompt**：Data Analyst Agent、chart code generation、composer 均增加 metadata 引用规则
- **字体缓存**：ChartTheme.initialize() 只执行一次字体扫描，FontManager 缓存 FontProperties
- **移除 rcParams 依赖**：所有文本元素改用显式 FontProperties
- **matplotlib 全图表类型中文支持**：不仅限于当前 6 种图表类型

## Capabilities

### New Capabilities

- `chart-font-management`: 统一字体管理与缓存，支持 matplotlib 所有 Artist 的中文 FontProperties
- `chart-palette`: 企业级调色板，固定 hex 值与中文颜色名映射
- `chart-result-metadata`: ChartResult 数据结构与 metadata.json 输出

### Modified Capabilities

- `chart-rendering`: 重构 ChartRenderer API，render() 返回 ChartResult 而非 str
- `chart-markdown-composition`: Markdown 生成改为引用 metadata，禁止 LLM 推断颜色

## Impact

- `ai_service/chart/` 全部模块（chart_theme.py, chart_renderer.py, chart_service.py, renderers/, utils/）
- `ai_service/tools/sandbox/tool.py` — preamble 适配新 API
- `ai_service/graph/nodes.py` — chart prompts 和 composer 改造
- `ai_service/db/migrations/002_seed_agents_and_setup.sql` — Data Analyst Agent system prompt
- 图表 API 返回格式变更（增加 metadata），前端按需适配
