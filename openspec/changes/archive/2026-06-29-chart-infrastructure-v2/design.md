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
    ERROR = PaletteColor("#EB5757", "红色")
    INFO = PaletteColor("#9B51E0", "紫色")
    NEUTRAL = PaletteColor("#828282", "灰色")

    SERIES = [PRIMARY, SECONDARY, SUCCESS, WARNING, ERROR, INFO, ...]

    @classmethod
    def get_series_colors(cls, n: int) -> list[PaletteColor]: ...
    @classmethod
    def get_color_name(cls, hex: str) -> str: ...
```

**Decision**: NamedTuple 而非 dict，保证字段类型安全。

**Why**: 当前 `PALETTE` 只是 hex list，Markdown 无法从 hex 推导颜色名。PaletteColor 绑定 hex 和 name_cn，metadata 中同时包含两者，Markdown 直接引用 `color_name`。

### 4. ChartResult 设计

```python
@dataclass
class ChartResult:
    image_path: str              # PNG 文件路径
    metadata: ChartMetadata      # 结构化元数据
    summary: str                 # AI 生成的一句话摘要

@dataclass
class ChartMetadata:
    title: str
    chart_type: str
    xlabel: str | None = None
    ylabel: str | None = None
    series: list[SeriesInfo] = field(default_factory=list)

@dataclass
class SeriesInfo:
    name: str
    color: str         # hex e.g. "#2F80ED"
    color_name: str    # 中文 e.g. "蓝色"
```

ChartMetadata.to_json() → 写入 metadata.json；ChartMetadata.to_markdown_hint() → 生成供 LLM 引用的文本片段。

### 5. ChartRenderer 重构

```
BEFORE:
  MatplotlibRenderer.render(code, output_path) → str (image_path)

AFTER:
  ChartRenderer.render(code, output_path) → ChartResult
  - exec(code, ctx) in subprocess/context
  - 用户代码调用 plt.savefig()
  - renderer 收集 figure 信息生成 ChartMetadata
  - 返回 ChartResult(image_path, metadata, summary)
```

**metadata 收集策略**: 不能要求 LLM 在代码中返回 metadata（不可靠）。改为：
1. exec 代码后，从 matplotlib figure state 提取 metadata
2. `fig.axes[0].get_title()`, `get_xlabel()`, `get_ylabel()`
3. `fig.legends` 或 `ax.get_legend()` 提取图例信息
4. 从 Palette 反查颜色名

**summary 生成**: renderer 不接受 LLM 调用。summary 在 exec 上下文中由用户代码设置 `__chart_result_summary__`，或 renderer 根据 title + series 自动生成模板化 summary。

### 6. Metadata 输出

```
chart_abc12345.png
chart_abc12345_metadata.json
```

同目录、同名（仅扩展名不同）。前端通过约定路径关联。

ChartService 在 render() 时负责写入 metadata.json。

### 7. Prompt 改造

**Chart Code Generation Prompt (`_CHART_CODE_PROMPT`)**:
- 注入 `cn_font = FontManager.get_cn_font()`
- 要求所有文本 API 使用 `fontproperties=cn_font`
- 要求从 `palette.SERIES` 取色，不自定义颜色
- 要求设置 `__chart_result_summary__` 变量（一句话摘要）
- 禁止 `plt.rcParams['font.sans-serif']` 手动设置

**Data Analyst Agent System Prompt**:
- 新增规则："颜色描述必须来自图表元数据(metadata)，不得根据图片推测"
- 新增规则："引用图例时使用元数据中的颜色名称，格式：`系列名（颜色名）`"

**Composer/Answer Prompt**:
- 接受 ChartResult 列表作为上下文
- 引用 metadata 中的 series/color_name 描述图表
- 禁止单独描述图表颜色

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 从 figure state 提取 metadata 不可靠（用户代码可能不设置 title/label） | metadata 字段全部 optional，自动提取 fallback 为空字符串 |
| FontProperties 增加代码侵入性，LLM 可能忘记使用 | Prompt 明确要求 + preamble 注入变量 + 自动检测代码中是否调用 rcParams 并警告 |
| Palette 颜色数有限（12色），超限时无合适颜色 | get_series_colors(n) 超限时使用循环 + 色相微调自动扩展 |
| 旧图表代码（无 FontProperties）仍可运行但中文乱码 | 渐进迁移：新增代码必须遵循新规范，旧代码在后续维护中迁移 |

## Migration Plan

1. 新增 FontManager、Palette、ChartResult 模块（不影响现有功能）
2. ChartRenderer.render() 签名改为返回 ChartResult（向后兼容：ChartResult.image_path 等同于旧返回值）
3. chart_service.py 适应新接口，增加 metadata.json 输出
4. Prompt 逐步更新（chart code prompt → data analyst prompt → composer prompt）
5. 无需数据库迁移或前端强制升级

## Open Questions

- ChartRenderer 从 figure state 自动提取 metadata 的覆盖率：需测试常见图表类型（line/bar/pie/scatter/hist/box/heatmap）确认 title/label/legend 可提取
- 是否需要 `font_name` 环境变量/配置文件支持？（暂定：自动发现 + 环境变量 `CHART_FONT_PATH` 可覆盖）
