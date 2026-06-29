# Comet Design Handoff

- Change: chart-single-source-truth
- Phase: design
- Mode: compact
- Context hash: 38006da60d63c72c48f49a86fdef31dd1c939fbf8ff80df500dac1979dd98237

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/chart-single-source-truth/proposal.md

- Source: openspec/changes/chart-single-source-truth/proposal.md
- Lines: 1-35
- SHA256: 8140e8bce5e8b1813478073eff7aed02b6d8420daa9fd08ab87e87432f5e5308

```md
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
```

## openspec/changes/chart-single-source-truth/design.md

- Source: openspec/changes/chart-single-source-truth/design.md
- Lines: 1-133
- SHA256: 23e0f369d7d5edfd0b047fb3ad1b8c36c2fa5c4461b810f3501cdb5710a9caa8

[TRUNCATED]

```md
## Context

当前 Data Analyst Agent 流程：Plan → 生成 matplotlib 代码 → execute_python 执行 → ChartService 上传 MinIO → Composer LLM 看图写 Markdown。LLM 看图推理导致 Hallucination（颜色/数值/趋势错误）。

chart-infrastructure-v2 已通过 spec 建立了 Palette、ChartResult、FontManager 的能力定义，但采用"从 matplotlib figure state 提取 metadata"的方案。该方案存在准确性风险：metadata 取决于 LLM 是否正确调用了 `ax.set_title()`、`ax.legend()` 等 API。

本次采用 ChartSpec 先行方案：LLM 代码先构建 ChartSpec 对象，ChartRenderer 从 ChartSpec 渲染并输出 ChartResult，metadata 直接由 ChartSpec 派生，从根本上消除 Hallucination。

## Goals / Non-Goals

**Goals:**
- ChartSpec 作为 Single Source of Truth，图片和 metadata 共享同一份数据
- ChartRenderer 自动从 ChartSpec 计算 summary（max/min/avg/trend）
- Markdown 引用 metadata，禁止 LLM 推测颜色/数值
- 存量 matplotlib 代码保持兼容（render(code, path) 仍然可用）

**Non-Goals:**
- 不修改 Planner、Multi-Agent、SpringBoot、SSE、数据库 schema、聊天流程、Tool Registry
- 不改变非图表代码的 execute_python 行为
- 不引入新的图表后端（plotly/echarts）
- 不重构 Agent Runtime

## Decisions

### 1. ChartSpec 先行 vs Figure State 提取

| 维度 | ChartSpec 先行 | Figure State 提取 |
|------|---------------|-------------------|
| metadata 准确性 | 100%（直接从 ChartSpec 派生） | 取决于 LLM 代码规范 |
| LLM 学习成本 | 需学习 ChartSpec API | 无需改变 |
| 维护性 | 类型安全，易扩展 | 依赖 matplotlib 内部状态 |

**决策：ChartSpec 先行。** Hallucination 是核心问题，必须从根源解决。ChartSpec API 足够简单，LLM 学习成本可控。

### 2. ChartSpec API 设计

类型特定字段方案：

```python
@dataclass
class ChartSpec:
    title: str
    chart_type: str  # line/bar/pie/scatter/histogram/heatmap
    xlabel: str | None = None
    ylabel: str | None = None
    figsize: tuple[int, int] = (12, 6)

    # 类型特定字段
    series: list[SeriesSpec] | None = None   # bar/line
    slices: list[SliceSpec] | None = None    # pie
    points: list[PointSpec] | None = None    # scatter
    data: list[list[float]] | None = None    # histogram/heatmap
    labels: list[str] | None = None          # x-axis labels

@dataclass
class SeriesSpec:
    name: str
    color: str          # hex, e.g. "#2F80ED"
    color_name: str     # Chinese, e.g. "蓝色"
    values: list[float]

@dataclass
class SliceSpec:
    label: str
    value: float
    color: str
    color_name: str

@dataclass
class PointSpec:
    x: float
    y: float
    label: str | None = None
```

`color_name` 由 Palette 提供，用户只选 hex 值，Palette 自动填充中文名。

### 3. Palette 设计

固定调色板，按语义分类：
```

Full source: openspec/changes/chart-single-source-truth/design.md

## openspec/changes/chart-single-source-truth/tasks.md

- Source: openspec/changes/chart-single-source-truth/tasks.md
- Lines: 1-63
- SHA256: b4caad5e085dbd8d97013008f89cda48b6bac75b36f8ee1fe3364c0b9aed2e0c

```md
## 1. Palette — 固定调色板

- [ ] 1.1 创建 `ai_service/chart/palette.py`：PaletteColor NamedTuple (hex + name_cn)，Palette 类包含 PRIMARY/SECONDARY/SUCCESS/WARNING/ERROR/INFO/NEUTRAL 常量
- [ ] 1.2 实现 `Palette.get_series_colors(n)` — 返回 n 个 PaletteColor，超限时 HSL 色相微调
- [ ] 1.3 实现 `Palette.get_color_name(hex)` — hex 到中文颜色名查询，未知 hex 返回自身
- [ ] 1.4 替换 `ai_service/chart/utils/color_utils.py` 中的旧 PALETTE，保持向后兼容导出

## 2. FontManager — 统一字体管理

- [ ] 2.1 创建 `ai_service/chart/font_manager.py`：FontManager 类，`initialize()` 扫描并缓存 FontProperties，`get_cn_font()` 返回缓存实例并自动初始化
- [ ] 2.2 实现跨平台字体发现：macOS (PingFang SC → Heiti SC → STHeiti → Arial Unicode MS)，Windows (Microsoft YaHei → SimHei → KaiTi)，Linux (Noto Sans CJK SC)
- [ ] 2.3 FontManager 幂等初始化 + fallback 策略：无中文字体时 WARNING 日志 + 默认 FontProperties

## 3. ChartSpec — 图表数据规范

- [ ] 3.1 创建 `ai_service/chart/chart_spec.py`：ChartSpec dataclass（title, chart_type, xlabel, ylabel, figsize, series, slices, points, data, labels）
- [ ] 3.2 创建 SeriesSpec/SliceSpec/PointSpec dataclass
- [ ] 3.3 SeriesSpec 自动填充 color_name：构造时若未提供 color_name，通过 Palette.get_color_name(color) 自动填充
- [ ] 3.4 ChartSpec.to_metadata() → 提取 title/chart_type/series/labels/colors 为 dict
- [ ] 3.5 ChartSpec.to_markdown_hint() → 生成 LLM 可引用的 metadata 文本片段

## 4. ChartResult — 统一返回结构

- [ ] 4.1 创建 `ai_service/chart/chart_result.py`：ChartResult(image_path, metadata, summary, stdout) dataclass
- [ ] 4.2 ChartResult.to_json() 序列化方法
- [ ] 4.3 ChartResult._compute_summary(values) 静态方法：从数值列表计算 max/min/avg/trend/growth_rate

## 5. ChartRenderer 重构

- [ ] 5.1 重构 `AbstractChartRenderer`：render() 返回 ChartResult；新增 render_from_spec(spec, output_path) 抽象方法
- [ ] 5.2 实现 `MatplotlibRenderer.render_from_spec(spec, output_path)` 返回 ChartResult，从 ChartSpec 渲染 matplotlib 图表
- [ ] 5.3 render_from_spec 支持全部 6 种图表类型：line/bar/pie/scatter/histogram/heatmap
- [ ] 5.4 重构 `MatplotlibRenderer.render(code, output_path)` 返回 ChartResult（向后兼容：image_path 与旧返回值一致）
- [ ] 5.5 渲染后输出 `{basename}_metadata.json` 与 PNG 同目录
- [ ] 5.6 exec 上下文注入 `cn_font` 变量（FontManager.get_cn_font()）和 Palette 导入

## 6. ChartService 适配

- [ ] 6.1 `ChartService.render()` 检测 `__chart_spec__` 变量：有则走 render_from_spec，无则走原流程
- [ ] 6.2 ChartService 返回格式更新：`{"type":"image","url":...,"metadata":{...},"summary":"..."}`
- [ ] 6.3 ChartTheme.initialize() 委托 FontManager 初始化，移除 rcParams 字体设置

## 7. Sandbox Tool 适配

- [ ] 7.1 修改 `CodeSandboxTool._build_preamble()` 注入 FontManager + Palette + ChartSpec + ChartResult 导入
- [ ] 7.2 preamble 注入 `cn_font = FontManager.get_cn_font()` 变量
- [ ] 7.3 ToolResult 增加可选的 metadata 字段，execute_python 返回时携带
- [ ] 7.4 移除 preamble 中仅依赖 rcParams 的 `ChartTheme.initialize()` 字体部分

## 8. Prompt 更新

- [ ] 8.1 更新 `_CHART_CODE_PROMPT`（nodes.py）：要求构建 ChartSpec + Palette 取色 + fontproperties=cn_font，禁止 rcParams
- [ ] 8.2 更新 `_build_composer_system_prompt`（nodes.py）：传递 metadata + summary，增加"数值/颜色必须来自 metadata，禁止推测"规则
- [ ] 8.3 更新 Data Analyst Agent system prompt（DB seed）：添加 metadata 引用规则、禁止图片推测、引用格式示例

## 9. 测试

- [ ] 9.1 新增 Palette 单元测试：颜色名查询、序列色获取、超限处理
- [ ] 9.2 新增 FontManager 单元测试：字体发现、缓存、fallback
- [ ] 9.3 新增 ChartSpec 单元测试：序列化、metadata 提取、color_name 自动填充
- [ ] 9.4 新增 ChartResult 单元测试：summary 计算（max/min/avg/trend）
- [ ] 9.5 新增 ChartRenderer 单元测试：render_from_spec 各图表类型、metadata 正确性
- [ ] 9.6 运行现有测试确认无回归（`test_chart_generator.py`, `test_data_analyst.py`）
```

## openspec/changes/chart-single-source-truth/specs/chart-font-management/spec.md

- Source: openspec/changes/chart-single-source-truth/specs/chart-font-management/spec.md
- Lines: 1-57
- SHA256: eab30fa11954881d7b9f74daec40b7fa7227290625581b01f7fe1a856ba83139

```md
## MODIFIED Requirements

### Requirement: FontManager provides cached FontProperties
FontManager SHALL discover and cache a Chinese-capable FontProperties instance at initialization time. Subsequent calls to `get_cn_font()` MUST return the cached instance without re-scanning the filesystem.

#### Scenario: First initialization caches font
- **WHEN** `FontManager.initialize()` is called for the first time
- **THEN** FontManager SHALL scan the system for Chinese-capable fonts, cache the FontProperties, and log the selected font name

#### Scenario: Subsequent calls use cache
- **WHEN** `FontManager.get_cn_font()` is called after initialization
- **THEN** FontManager MUST return the cached FontProperties without any filesystem scan

#### Scenario: Re-initialization uses cache
- **WHEN** `FontManager.initialize()` is called multiple times
- **THEN** Only the first call SHALL perform a font scan; subsequent calls MUST return immediately

### Requirement: FontProperties explicitly passed to all matplotlib text APIs
All matplotlib Artist text elements SHALL receive `fontproperties=<cn_font>` explicitly. The system MUST NOT rely on `plt.rcParams` for Chinese font rendering.

#### Scenario: Title uses FontProperties
- **WHEN** chart code calls `ax.set_title("中文标题", fontproperties=cn_font)`
- **THEN** The title SHALL render Chinese characters correctly without tofu boxes

#### Scenario: Legend uses FontProperties
- **WHEN** chart code calls `ax.legend(prop=cn_font)`
- **THEN** Legend text SHALL render Chinese characters correctly

#### Scenario: Table cells use FontProperties
- **WHEN** chart code creates a table via `ax.table()` and sets `cell.get_text().set_fontproperties(cn_font)` for every cell
- **THEN** All table cell text SHALL render Chinese characters correctly

#### Scenario: Annotation uses FontProperties
- **WHEN** chart code calls `ax.annotate("中文注释", ..., fontproperties=cn_font)`
- **THEN** Annotation text SHALL render Chinese characters correctly

#### Scenario: Tick labels use FontProperties
- **WHEN** chart code applies `plt.setp(ax.get_xticklabels(), fontproperties=cn_font)`
- **THEN** Tick labels SHALL render Chinese characters correctly

### Requirement: Font discovery covers platform-specific fonts
FontManager SHALL search a prioritized platform-specific font list and return the first available font.

#### Scenario: macOS font discovery
- **WHEN** running on macOS
- **THEN** FontManager SHALL search in order: PingFang SC, Heiti SC, STHeiti, Arial Unicode MS

#### Scenario: Fallback when no Chinese font found
- **WHEN** no Chinese-capable font is found on the system
- **THEN** FontManager SHALL return a default FontProperties, log a WARNING, and allow chart generation to continue with potentially missing Chinese glyphs

### Requirement: FontManager auto-initializes on first access
`FontManager.get_cn_font()` SHALL trigger initialization if not already done, so callers do not need to explicitly call `initialize()`.

#### Scenario: First get_cn_font() triggers init
- **WHEN** `FontManager.get_cn_font()` is called without prior `initialize()`
- **THEN** FontManager SHALL auto-initialize, discover fonts, and return the cached FontProperties
```

## openspec/changes/chart-single-source-truth/specs/chart-markdown-composition/spec.md

- Source: openspec/changes/chart-single-source-truth/specs/chart-markdown-composition/spec.md
- Lines: 1-53
- SHA256: dbe032c1052d5f7ede8fe900807160450286f8717705b64c0aaae7eb2debf8c6

```md
## MODIFIED Requirements

### Requirement: Markdown color descriptions reference metadata
When composing Markdown reports, the system SHALL reference chart metadata (`ChartResult.metadata` and `ChartResult.summary`) for all color descriptions. The system MUST NOT allow the LLM to infer or guess colors from the chart image.

#### Scenario: Color description from metadata
- **WHEN** generating Markdown for a chart with metadata series `[{"name":"GDP","color":"#2F80ED","color_name":"蓝色"}]`
- **THEN** The Markdown SHALL describe GDP as "GDP（蓝色）", using the color_name from metadata

#### Scenario: No guessed color descriptions
- **WHEN** the chart has no color information in metadata
- **THEN** The Markdown SHALL NOT include any color-based descriptions (e.g., "红色表示...", "蓝色柱状图...")

#### Scenario: Reference summary text
- **WHEN** ChartResult.summary contains "GDP 在 2020-2024 年间保持稳定增长"
- **THEN** The Markdown SHALL include this summary text verbatim, framed as a chart description

### Requirement: Chart code prompt requires ChartSpec + Palette + FontManager
The chart code generation prompt SHALL instruct the LLM to construct `ChartSpec` objects with Palette colors and use `fontproperties=cn_font` for all text elements. It SHALL explicitly prohibit `plt.rcParams['font.sans-serif']` and random color generation.

#### Scenario: Prompt includes ChartSpec instruction
- **WHEN** examining the chart code generation prompt
- **THEN** It SHALL contain instruction to build ChartSpec with `chart_type`, `title`, `series` fields before calling `render_from_spec()`

#### Scenario: Prompt includes Palette instruction
- **WHEN** examining the chart code generation prompt
- **THEN** It SHALL instruct to use `Palette.PRIMARY`, `Palette.SECONDARY` etc. for series colors

#### Scenario: Prompt includes FontProperties instruction
- **WHEN** examining the chart code generation prompt
- **THEN** It SHALL contain explicit instruction to use `cn_font` (FontProperties) for all text APIs

#### Scenario: Prompt prohibits rcParams
- **WHEN** examining the chart code generation prompt
- **THEN** It SHALL explicitly forbid setting `plt.rcParams['font.sans-serif']`

### Requirement: Data Analyst prompt requires metadata-based color attribution
The Data Analyst Agent system prompt SHALL require that all color descriptions come from chart metadata, not from visual interpretation of the image.

#### Scenario: Prompt forbids image-based color guessing
- **WHEN** examining the Data Analyst Agent system prompt
- **THEN** It SHALL include a rule stating that colors must be sourced from Chart Metadata, not inferred from the image

### Requirement: Composer prompt passes metadata to LLM
The composer system prompt SHALL include chart metadata and summary for each chart artifact, enabling the LLM to reference them without visual inference.

#### Scenario: Composer receives metadata per chart
- **WHEN** building the composer prompt for a step with chart artifacts
- **THEN** each chart artifact entry SHALL include its `metadata` (title, chart_type, series with color_name) and `summary` text

#### Scenario: Composer prompt prohibits value guessing
- **WHEN** examining the composer system prompt
- **THEN** It SHALL include a rule that numerical values and trends MUST come from the provided metadata/summary, not from visual estimation of the chart image
```

## openspec/changes/chart-single-source-truth/specs/chart-palette/spec.md

- Source: openspec/changes/chart-single-source-truth/specs/chart-palette/spec.md
- Lines: 1-38
- SHA256: 5b2828a57e09601390f90bd256fb3db2b0ed039b47bd2fbfd8aa7266bcac62bb

```md
## MODIFIED Requirements

### Requirement: Palette provides named colors with hex and Chinese color names
Each palette color SHALL be a `PaletteColor` with both `hex` and `name_cn` fields. The Palette SHALL expose named constants: PRIMARY (#2F80ED, 蓝色), SECONDARY (#27AE60, 绿色), SUCCESS (#219653, 深绿), WARNING (#F2994A, 橙色), ERROR (#EB5757, 红色), INFO (#9B51E0, 紫色), NEUTRAL (#828282, 灰色).

#### Scenario: Primary color has name
- **WHEN** accessing `Palette.PRIMARY`
- **THEN** The color SHALL have `hex="#2F80ED"` and `name_cn="蓝色"`

#### Scenario: All semantic constants have non-empty name_cn
- **WHEN** iterating over `[Palette.PRIMARY, Palette.SECONDARY, Palette.SUCCESS, Palette.WARNING, Palette.ERROR]`
- **THEN** each color SHALL have a non-empty `name_cn` field

#### Scenario: Color name lookup by hex
- **WHEN** calling `Palette.get_color_name("#2F80ED")`
- **THEN** The system SHALL return `"蓝色"`

#### Scenario: Unknown hex returns hex string
- **WHEN** calling `Palette.get_color_name("#unknown")`
- **THEN** The system SHALL return the hex string itself as fallback

### Requirement: Series colors retrieved from palette
All chart series SHALL use colors from the Palette, not randomly generated colors.

#### Scenario: Get N series colors
- **WHEN** calling `Palette.get_series_colors(3)`
- **THEN** The system SHALL return the first 3 palette colors in order: PRIMARY, SECONDARY, SUCCESS

#### Scenario: Exceeding available colors cycles with hue shift
- **WHEN** calling `Palette.get_series_colors(15)` (exceeding the 12 base colors)
- **THEN** The system SHALL return 15 colors, with extra colors generated by cycling and adjusting hue to ensure distinctiveness

### Requirement: Palette color count matches base palette
The base palette SHALL contain at least 7 named constants covering the standard semantic categories.

#### Scenario: Palette has minimum constants
- **WHEN** checking the number of named Palette constants
- **THEN** The count SHALL be >= 7 (PRIMARY, SECONDARY, SUCCESS, WARNING, ERROR, INFO, NEUTRAL)
```

## openspec/changes/chart-single-source-truth/specs/chart-rendering/spec.md

- Source: openspec/changes/chart-single-source-truth/specs/chart-rendering/spec.md
- Lines: 1-46
- SHA256: 4e05716f33657337ec85959a4ff23cf0554a931754b8b2ea76a91632f07f3f43

```md
## MODIFIED Requirements

### Requirement: ChartRenderer.render() returns ChartResult
`ChartRenderer.render(code, output_path)` SHALL return a `ChartResult` object instead of a plain string. The ChartResult SHALL contain the image path, structured metadata extracted from the rendered figure, and a summary.

#### Scenario: render returns ChartResult
- **WHEN** `renderer.render(code, output_path)` completes successfully
- **THEN** The return value SHALL be a `ChartResult` with `image_path` pointing to the generated PNG

#### Scenario: metadata extracted from figure
- **WHEN** user code sets `ax.set_title("GDP Growth")` and `ax.set_xlabel("Year")`
- **THEN** `ChartResult.metadata.title` SHALL be "GDP Growth" and `ChartResult.metadata.xlabel` SHALL be "Year"

#### Scenario: Legacy code compatibility
- **WHEN** existing code accesses `ChartResult.image_path`
- **THEN** It SHALL return the same string value as the old `render()` return value (the PNG file path)

### Requirement: ChartRenderer.render_from_spec renders from ChartSpec
`ChartRenderer.render_from_spec(spec: ChartSpec, output_path)` SHALL render a chart from a ChartSpec object and return a `ChartResult` with metadata directly derived from the ChartSpec.

#### Scenario: Bar chart from ChartSpec
- **WHEN** `render_from_spec(spec, output_path)` is called with a bar ChartSpec containing 2 series
- **THEN** A bar chart SHALL be rendered with correctly colored bars, legend, title, and axis labels

#### Scenario: Metadata from ChartSpec
- **WHEN** `render_from_spec(spec, output_path)` returns a ChartResult
- **THEN** `ChartResult.metadata.title` SHALL equal `spec.title` and `ChartResult.metadata.series` SHALL equal `spec.series`

#### Scenario: Pie chart from ChartSpec
- **WHEN** `render_from_spec(spec, output_path)` is called with a pie ChartSpec containing slices
- **THEN** A pie chart SHALL be rendered with correctly colored and labeled slices

### Requirement: All matplotlib charts support Chinese text
Every matplotlib chart type SHALL render Chinese text correctly across all text elements, not only those covered by rcParams.

#### Scenario: Box plot Chinese labels
- **WHEN** a box plot is generated with Chinese title and labels
- **THEN** All text elements SHALL display Chinese characters without tofu boxes

#### Scenario: Histogram Chinese labels
- **WHEN** a histogram is generated with Chinese title and axis labels
- **THEN** All text elements SHALL display Chinese characters correctly

#### Scenario: Heatmap Chinese annotations
- **WHEN** a heatmap is generated with Chinese annotations via `ax.text()`
- **THEN** All annotation text SHALL display Chinese characters correctly
```

## openspec/changes/chart-single-source-truth/specs/chart-result-metadata/spec.md

- Source: openspec/changes/chart-single-source-truth/specs/chart-result-metadata/spec.md
- Lines: 1-48
- SHA256: f76c1b679c41e52959d8c753acecc105f7bd508e2ee04a68ae1a7e49fa241d9f

```md
## MODIFIED Requirements

### Requirement: ChartResult contains image path, metadata, and summary
Every chart generation SHALL return a `ChartResult` object with `image_path`, `metadata`, and `summary` fields.

#### Scenario: ChartResult created after chart generation
- **WHEN** a chart is successfully rendered
- **THEN** The returned ChartResult SHALL contain a non-empty `image_path`, a `metadata` object, and a `summary` string

### Requirement: ChartMetadata includes title, chart type, and series info
The metadata SHALL contain `title`, `chart_type`, and `series` fields, with optional `xlabel` and `ylabel`.

#### Scenario: Bar chart metadata
- **WHEN** a bar chart titled "Sales Report" is generated with two series "Product A" and "Product B"
- **THEN** `metadata.title` SHALL be "Sales Report", `metadata.chart_type` SHALL be "bar", and `metadata.series` SHALL have 2 entries each with `name`, `color` (hex), and `color_name` (Chinese)

### Requirement: metadata.json output alongside PNG
Every chart PNG SHALL be accompanied by a `metadata.json` file in the same directory with the same base filename.

#### Scenario: Metadata JSON output
- **WHEN** chart is saved as `/tmp/chart_abc12345.png`
- **THEN** a file `/tmp/chart_abc12345_metadata.json` SHALL exist and contain valid JSON with title, chart_type, series, xlabel, ylabel fields

#### Scenario: Metadata JSON is valid JSON
- **WHEN** reading the metadata.json file
- **THEN** The file SHALL parse as valid JSON with all required fields present

### Requirement: Series info links color to name
Each series entry in metadata SHALL contain both the hex color and its Chinese color name from the Palette.

#### Scenario: Series color_name matches Palette
- **WHEN** a series uses the PRIMARY color `#2F80ED`
- **THEN** The series SHALL have `color="#2F80ED"` and `color_name="蓝色"`

### Requirement: Summary auto-computed from chart data
`ChartResult.summary` SHALL be automatically computed by ChartRenderer from the ChartSpec data. It SHALL include at minimum the maximum value, minimum value, and average of all numeric data.

#### Scenario: Summary contains statistics for bar chart
- **WHEN** a bar chart has series with values [100, 200, 150, 300, 250]
- **THEN** `ChartResult.summary` SHALL include max=300, min=100, avg=200

#### Scenario: Summary includes trend for time series
- **WHEN** a line chart has series values [100, 120, 150, 180, 200]
- **THEN** `ChartResult.summary` SHALL indicate an upward trend

#### Scenario: Summary is empty when no numeric data
- **WHEN** a chart has no numeric series/slices/points data to compute statistics from
- **THEN** `ChartResult.summary` SHALL be an empty string
```

## openspec/changes/chart-single-source-truth/specs/chart-spec/spec.md

- Source: openspec/changes/chart-single-source-truth/specs/chart-spec/spec.md
- Lines: 1-30
- SHA256: 7f040540f272fa9320ed1e49b8d5af05ea89cb6e2b8b228e2f1f3237b50ea675

```md
## ADDED Requirements

### Requirement: ChartSpec provides type-specific chart definition
The system SHALL provide a `ChartSpec` dataclass that serves as the Single Source of Truth for chart rendering and metadata. ChartSpec SHALL support type-specific fields for different chart types.

#### Scenario: Bar chart with series
- **WHEN** constructing a ChartSpec with `chart_type="bar"`, `title="Sales Report"`, and `series=[SeriesSpec(name="Product A", color="#2F80ED", color_name="蓝色", values=[100, 200, 150])]`
- **THEN** the ChartSpec SHALL store all fields for rendering and metadata extraction

#### Scenario: Pie chart with slices
- **WHEN** constructing a ChartSpec with `chart_type="pie"`, `slices=[SliceSpec(label="A", value=30, color="#2F80ED", color_name="蓝色")]`
- **THEN** the ChartSpec SHALL store pie-specific slice data

#### Scenario: Scatter chart with points
- **WHEN** constructing a ChartSpec with `chart_type="scatter"`, `points=[PointSpec(x=1.0, y=2.5, label="sample")]`
- **THEN** the ChartSpec SHALL store scatter-specific point data

### Requirement: SeriesSpec links data to color identity
Each series in a chart SHALL be described by a `SeriesSpec` containing `name`, `color` (hex), `color_name` (Chinese), and `values` (list of floats).

#### Scenario: SeriesSpec with all fields populated
- **WHEN** creating `SeriesSpec(name="GDP", color="#2F80ED", color_name="蓝色", values=[120, 150, 180])`
- **THEN** all fields SHALL be accessible for rendering and metadata output

### Requirement: Palette color assignment fills color_name automatically
When constructing ChartSpec with Palette constants, the `color_name` field SHALL be automatically derived from the Palette's color-to-name mapping.

#### Scenario: Series uses Palette.SUCCESS
- **WHEN** `SeriesSpec(name="Revenue", color=Palette.SUCCESS.hex, values=[...])` is created
- **THEN** `color_name` SHALL be populated as `Palette.SUCCESS.name_cn` (e.g., "深绿") if not explicitly provided
```

