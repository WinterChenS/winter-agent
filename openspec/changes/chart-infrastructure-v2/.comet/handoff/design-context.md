# Comet Design Handoff

- Change: chart-infrastructure-v2
- Phase: design
- Mode: compact
- Context hash: debddf4219f55d3493198f4f126a9aaff1159c7387ed5da2e80940cae371ad17

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/chart-infrastructure-v2/proposal.md

- Source: openspec/changes/chart-infrastructure-v2/proposal.md
- Lines: 1-37
- SHA256: d90066c128966bb67d6bf04f1355ad172d5e311fd1d833ae2977efa440231896

```md
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
```

## openspec/changes/chart-infrastructure-v2/design.md

- Source: openspec/changes/chart-infrastructure-v2/design.md
- Lines: 1-194
- SHA256: b66bd53cb8c1c1c29ab0b7055a4b0d140e821655b8e08ff3f5fe69bc841c443a

[TRUNCATED]

```md
## Context

当前 `ai_service/chart/` 模块提供基础的 matplotlib 图表生成能力：

- `ChartTheme.initialize()` 通过 rcParams 设置中文字体、DPI、figsize
- `_find_chinese_font()` 返回字体名字符串，每次调用重新扫描
- `MatplotlibRenderer.render(code, output_path)` exec 用户代码并保存 PNG
- `ChartService.render(code)` 返回 `{"type":"image","url":...}`
- `PALETTE` 提供 12 个 hex 色值，但无色名映射

核心缺陷：rcParams 只能覆盖全局默认，对 ax.text()/table/annotate() 等显式创建 Artist 的场景无效，导致中文乱码。LLM 生成 Markdown 时自行描述颜色，与图中实际颜色不一致。

## Goals / Non-Goals

**Goals:**
- FontManager 启动时一次性发现并缓存 FontProperties，所有 matplotlib Artist 显式传入 fontproperties
- Palette 提供完整的 hex → color_name 映射，所有图表统一使用
- ChartRenderer.render() 返回 ChartResult（image_path + metadata + summary）
- 每张图表同时输出 metadata.json
- Markdown 生成引用 metadata，禁止 LLM 推测颜色
- matplotlib 全图表类型中文支持

**Non-Goals:**
- 不修改 MinIO 存储层
- 不重构前端 ECharts/Image 渲染
- 不引入 matplotlib 以外的图表库
- 不改变现有 SSE 事件协议

## Decisions

### 1. FontManager 设计

```
FontManager (singleton/module-level)
├── _font_properties: FontProperties | None
├── _font_name: str
├── initialize() → None         # 启动时调用一次，扫描并缓存
├── get_cn_font() → FontProperties  # 返回缓存，不动态扫描
└── get_font_name() → str
```

**Decision**: 模块级单例而非类实例。Python 模块天然单例，避免复杂的依赖注入。

**Why**: 当前 `_find_chinese_font()` 返回字符串，调用方需要用 `plt.rcParams['font.sans-serif']` 间接设置，且不能覆盖所有 Artist。改为返回 FontProperties 后，调用方可直接传入所有文本 API。

**Font discovery**: 按平台优先级搜索（macOS: PingFang SC → Heiti SC → STHeiti → Arial Unicode MS; Windows: Microsoft YaHei → SimHei → KaiTi; Linux: Noto Sans CJK SC → Noto Sans SC → WenQuanYi Micro Hei），找到第一个即缓存。

**Fallback**: 无可用中文字体时，get_cn_font() 返回默认 FontProperties，记录 WARNING 日志，图表仍生成但中文不保证显示。

### 2. FontProperties 强制规则

所有 matplotlib 文本 API 必须显式传入 fontproperties：

| API | 参数 |
|-----|------|
| `ax.set_title()` | `fontproperties=cn_font` |
| `ax.set_xlabel()` | `fontproperties=cn_font` |
| `ax.set_ylabel()` | `fontproperties=cn_font` |
| `ax.legend()` | `prop=cn_font` |
| `ax.text()` | `fontproperties=cn_font` |
| `ax.annotate()` | `fontproperties=cn_font` |
| `ax.tick_params()` | 通过 `plt.setp(ax.get_xticklabels(), fontproperties=cn_font)` |
| `plt.suptitle()` | `fontproperties=cn_font` |
| `ax.table()` | `cell.get_text().set_fontproperties(cn_font)` |
| `fig.colorbar()` | `cbar.set_label(..., fontproperties=cn_font)` |

**Implementation**: `MatplotlibRenderer.render()` 在 exec 用户代码前，注入 `cn_font = FontManager.get_cn_font()` 到 exec context。在 Chart code generation prompt 中明确要求使用 `cn_font` 变量，不依赖 rcParams。

### 3. Palette 设计

```python
class PaletteColor(NamedTuple):
    hex: str
    name_cn: str  # 中文颜色名

class Palette:
    PRIMARY = PaletteColor("#2F80ED", "蓝色")
    SECONDARY = PaletteColor("#27AE60", "绿色")
    SUCCESS = PaletteColor("#219653", "深绿")
    WARNING = PaletteColor("#F2994A", "橙色")
```

Full source: openspec/changes/chart-infrastructure-v2/design.md

## openspec/changes/chart-infrastructure-v2/tasks.md

- Source: openspec/changes/chart-infrastructure-v2/tasks.md
- Lines: 1-59
- SHA256: 27e63b6ac90e086e7f38802fe784d58867562ed59eeb8062394962ca6529a1c5

```md
## 1. FontManager — 统一字体管理

- [ ] 1.1 创建 `ai_service/chart/font_manager.py`：FontManager 类，`initialize()` 扫描并缓存 FontProperties，`get_cn_font()` 返回缓存实例
- [ ] 1.2 实现跨平台字体发现：macOS (PingFang SC → Heiti SC → STHeiti → Arial Unicode MS)，Windows (Microsoft YaHei → SimHei → KaiTi)，Linux (Noto Sans CJK SC → Noto Sans SC → WenQuanYi Micro Hei)
- [ ] 1.3 FontManager 幂等初始化：多次调用 `initialize()` 只扫描一次，日志记录选中字体
- [ ] 1.4 Fallback 策略：无中文字体时返回默认 FontProperties + WARNING 日志

## 2. Palette — 企业调色板

- [ ] 2.1 创建 `ai_service/chart/palette.py`：PaletteColor NamedTuple (hex + name_cn)，Palette 类包含 PRIMARY/SECONDARY/SUCCESS/WARNING/ERROR/INFO/NEUTRAL 常量
- [ ] 2.2 实现 `Palette.get_series_colors(n)` — 返回 n 个 PaletteColor，超限时循环+色相微调
- [ ] 2.3 实现 `Palette.get_color_name(hex)` — hex 到中文颜色名查询，未知 hex 返回自身
- [ ] 2.4 替换 `ai_service/chart/utils/color_utils.py` 中的旧 PALETTE，保持向后兼容导出

## 3. ChartResult + ChartMetadata — 统一数据结构

- [ ] 3.1 创建 `ai_service/chart/chart_result.py`：ChartResult(image_path, metadata, summary) 和 ChartMetadata(title, chart_type, xlabel, ylabel, series) 数据类
- [ ] 3.2 ChartMetadata.to_json() 序列化方法，ChartMetadata.to_markdown_hint() 生成 LLM 可引用的文本片段
- [ ] 3.3 SeriesInfo 数据类：name + color(hex) + color_name(中文)

## 4. ChartRenderer 重构

- [ ] 4.1 重构 `MatplotlibRenderer.render()` 返回 ChartResult 替代 str
- [ ] 4.2 exec 上下文注入 `cn_font` 变量（FontManager.get_cn_font()）
- [ ] 4.3 从 matplotlib figure state 提取 metadata（title/xlabel/ylabel/legend/series）
- [ ] 4.4 支持 `__chart_result_summary__` 用户变量注入 summary，或自动生成模板化 summary
- [ ] 4.5 确保 `ChartResult.image_path` 与旧返回值兼容

## 5. Metadata JSON 输出

- [ ] 5.1 ChartRenderer 在保存 PNG 的同时输出 `{basename}_metadata.json`
- [ ] 5.2 修改 `ChartService.render()` 返回包含 metadata 的响应
- [ ] 5.3 ChartService 返回格式更新：`{"type":"image","url":...,"metadata":{...},"summary":"..."}`

## 6. ChartTheme 适配

- [ ] 6.1 重构 `ChartTheme.initialize()` 委托 FontManager 初始化，移除 rcParams 字体设置
- [ ] 6.2 ChartTheme 保留 DPI/figsize/grid/fontsize 等非字体配置

## 7. Sandbox Tool 适配

- [ ] 7.1 修改 `CodeSandboxTool._build_preamble()` 注入 `from chart.font_manager import FontManager; cn_font = FontManager.get_cn_font()`
- [ ] 7.2 preamble 注入 `from chart.palette import Palette` 和 Palette 色板变量
- [ ] 7.3 移除 preamble 中仅依赖 rcParams 的 `ChartTheme.initialize()` 调用（或改为仅设置非字体样式）

## 8. Prompt 更新

- [ ] 8.1 更新 `_CHART_CODE_PROMPT`（nodes.py）：要求所有文本 API 使用 `fontproperties=cn_font`，禁止 `plt.rcParams['font.sans-serif']`，从 Palette 取色，设置 summary
- [ ] 8.2 更新 Composer prompt（`_build_composer_system_prompt`）：传递 ChartResult 列表，要求引用 metadata 颜色描述，禁止自行推测颜色
- [ ] 8.3 更新 Data Analyst Agent system prompt（DB seed）：添加"颜色描述必须来自 Chart Metadata"规则，添加"引用图例格式：系列名（颜色名）"规则

## 9. 清理与测试

- [ ] 9.1 删除旧 `_find_chinese_font()` 函数（chart_theme.py），全部委托 FontManager
- [ ] 9.2 运行现有测试确认无回归（`test_chart_generator.py`, `test_chart_validators.py`, `test_data_analyst.py`）
- [ ] 9.3 新增 FontManager 单元测试：字体发现、缓存、fallback
- [ ] 9.4 新增 Palette 单元测试：颜色名查询、序列色获取、超限处理
- [ ] 9.5 新增 ChartRenderer 单元测试：ChartResult 返回、metadata 提取
- [ ] 9.6 端到端验证：生成线图/柱状图/饼图/散点图/直方图/热力图，确认中文正常、metadata 正确
```

## openspec/changes/chart-infrastructure-v2/specs/chart-font-management/spec.md

- Source: openspec/changes/chart-infrastructure-v2/specs/chart-font-management/spec.md
- Lines: 1-50
- SHA256: 7718ed0b10e9355cd1c88aa702e155cbc78df2ebe4f46eb391c3b8c7b7eb45f4

```md
## ADDED Requirements

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
```

## openspec/changes/chart-infrastructure-v2/specs/chart-markdown-composition/spec.md

- Source: openspec/changes/chart-infrastructure-v2/specs/chart-markdown-composition/spec.md
- Lines: 1-34
- SHA256: 8386b486711654eb559ed0925371f8a83822efe9e588721b847081d4dee93a71

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

### Requirement: Chart code prompt prohibits rcParams font configuration
The chart code generation prompt SHALL instruct the LLM to use `fontproperties=cn_font` for all text elements and SHALL explicitly prohibit `plt.rcParams['font.sans-serif']` configuration.

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
```

## openspec/changes/chart-infrastructure-v2/specs/chart-palette/spec.md

- Source: openspec/changes/chart-infrastructure-v2/specs/chart-palette/spec.md
- Lines: 1-34
- SHA256: df068e5201f95f65946a5a303dbeae2e08e5ee3a206368f9427875b96096f28d

```md
## ADDED Requirements

### Requirement: Palette provides named colors with hex and Chinese color names
Each palette color SHALL include both a hex value and a Chinese color name (e.g., `("蓝色", "#2F80ED")`).

#### Scenario: Primary color has name
- **WHEN** accessing `Palette.PRIMARY`
- **THEN** The color SHALL have `hex="#2F80ED"` and `name_cn="蓝色"`

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
The base palette SHALL contain at least 8 colors covering the standard categories.

#### Scenario: Palette has minimum colors
- **WHEN** checking `len(Palette.SERIES)`
- **THEN** The count SHALL be >= 8
```

## openspec/changes/chart-infrastructure-v2/specs/chart-rendering/spec.md

- Source: openspec/changes/chart-infrastructure-v2/specs/chart-rendering/spec.md
- Lines: 1-31
- SHA256: 84ffc6615d0b1dcf363b6b4ed8e231705550cc0144a52d0beddd4ffec3b20541

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

## openspec/changes/chart-infrastructure-v2/specs/chart-result-metadata/spec.md

- Source: openspec/changes/chart-infrastructure-v2/specs/chart-result-metadata/spec.md
- Lines: 1-33
- SHA256: 4ae9ad6f1bee322cfb5aec407a6306a805dc07d83e8d4e99bae9fd30be8ede39

```md
## ADDED Requirements

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
```

