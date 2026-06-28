---
comet_change: chart-infrastructure-v2
role: technical-design
canonical_spec: openspec
---

# Chart Infrastructure v2 — Technical Design

## 1. 数据流架构

```
User Request
    │
    ▼
planning_node → execution_node
                     │
                     ▼
┌──────────────────────────────────────────┐
│          _generate_chart_code()           │
│  Prompt 要求:                             │
│  ✅ fontproperties=cn_font (所有文本)     │
│  ✅ 颜色从 Palette 取                     │
│  ✅ __chart_metadata__ = {...}            │
│  ❌ 禁止 rcParams 字体设置                │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│        MatplotlibRenderer.render()        │
│  1. FontManager.initialize() (幂等)       │
│  2. 注入 cn_font 到 exec context          │
│  3. exec(code, ctx)                       │
│  4. L1: 提取 __chart_metadata__           │
│  5. L2: figure state 降级补缺             │
│  6. 字体校验: Text Artist fontproperties  │
│  7. 输出 PNG + metadata.json              │
│  8. 返回 ChartResult                      │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│           ChartService.render()           │
│  → MinIO upload (PNG + metadata.json)    │
│  → SSE: image.uploaded                    │
│  → SSE: chart.metadata ✨                 │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│         Composer Node                     │
│  接收 ChartResult 列表                    │
│  引用 metadata.series[].color_name        │
│  引用 metadata.summary                    │
│  ❌ 禁止自创颜色描述                      │
└──────────────────────────────────────────┘
```

## 2. 模块设计

### 2.1 FontManager (`font_manager.py`)

模块级单例，通过类方法访问。

```
FontManager
├── _font_properties: FontProperties | None
├── _font_name: str
├── _initialized: bool
├── initialize(force=False) → None     # 幂等，首次扫描并缓存
├── get_cn_font() → FontProperties     # 返回缓存，未初始化时自动初始化
├── get_font_name() → str              # 日志用
├── _discover() → FontProperties       # 跨平台发现
├── _validate_chinese(fp) → bool       # CJK 支持验证
└── validate_figure_fonts(fig) → list[str]  # 字体合规扫描
```

**字体发现优先级**：
- macOS: PingFang SC → Heiti SC → STHeiti → Arial Unicode MS
- Windows: Microsoft YaHei → SimHei → KaiTi
- Linux: Noto Sans CJK SC → Noto Sans SC → WenQuanYi Micro Hei

**Fallback**: 无可用字体时返回默认 FontProperties + WARNING 日志。

**环境变量**: `CHART_FONT_PATH` 可覆盖，直接使用指定字体文件路径创建 FontProperties。

**字体校验**: `validate_figure_fonts(fig)` 遍历 `fig.findobj(match=Text)`，检查每个 Text Artist 的 fontproperties，返回未设置或为默认值的警告列表。

### 2.2 Palette (`palette.py`)

```python
class PaletteColor(NamedTuple):
    hex: str       # "#2F80ED"
    name_cn: str   # "蓝色"

class Palette:
    # 基础 8 色
    PRIMARY   = PaletteColor("#2F80ED", "蓝色")
    SECONDARY = PaletteColor("#27AE60", "绿色")
    SUCCESS   = PaletteColor("#219653", "深绿")
    WARNING   = PaletteColor("#F2994A", "橙色")
    ERROR     = PaletteColor("#EB5757", "红色")
    INFO      = PaletteColor("#9B51E0", "紫色")
    PINK      = PaletteColor("#E91E63", "粉红")
    CYAN      = PaletteColor("#00BCD4", "青色")

    # 扩展 4 色
    EXT_AMBER    = PaletteColor("#FFC107", "琥珀")
    EXT_TEAL     = PaletteColor("#009688", "青绿")
    EXT_INDIGO   = PaletteColor("#3F51B5", "靛蓝")
    EXT_BROWN    = PaletteColor("#795548", "棕色")

    SERIES = [PRIMARY, ..., EXT_BROWN]  # 12 色

    # Key methods
    get_series_colors(n: int) → list[PaletteColor]
    get_color_name(hex: str) → str
```

**超限策略**: n ≤ 12 直接切片；n > 12 循环基色 + 色相偏移 30° 生成变体（通过 matplotlib.colors.rgb_to_hsv/hsv_to_rgb），变体命名为基色名+序号。

**兼容**: 旧 `color_utils.py` 的 `PALETTE` list 保留为 `[pc.hex for pc in Palette.SERIES]`。

### 2.3 ChartResult + ChartMetadata (`chart_result.py`)

```python
@dataclass
class SeriesInfo:
    name: str
    color: str       # hex
    color_name: str  # 中文

@dataclass
class ChartMetadata:
    title: str
    chart_type: str
    xlabel: str = ""
    ylabel: str = ""
    series: list[SeriesInfo] = field(default_factory=list)

    def to_dict(self) -> dict: ...
    def to_markdown_hint(self) -> str: ...

@dataclass
class ChartResult:
    image_path: str
    metadata: ChartMetadata
    summary: str = ""
```

`to_markdown_hint()` 生成 LLM 引用文本：
```
图表: GDP增长率 (bar)
 - GDP: 蓝色 (#2F80ED)
 - CPI: 绿色 (#27AE60)
摘要: GDP在2020-2024年间稳定增长
```

### 2.4 MatplotlibRenderer (`renderers/matplotlib_renderer.py`)

**核心流程**：
```
render(code, output_path) → ChartResult
  1. FontManager.initialize()           # 幂等
  2. plt.close("all")                   # 清理
  3. 构建 exec context:
     - __output_path__, plt, np
     - cn_font: FontManager.get_cn_font()
     - __chart_metadata__: None
  4. exec(code, ctx)
  5. _extract_metadata(ctx) → ChartMetadata
  6. _validate_fonts() → list[str]
  7. _save_metadata(output_path, metadata)
  8. 返回 ChartResult
```

**Metadata 两级降级**:
```
L1: __chart_metadata__ dict 存在？
  ├─ Yes → 用它构建，缺失字段 L2 补充
  └─ No  → L2: figure state 提取
             title   ← ax.get_title()
             xlabel  ← ax.get_xlabel()
             ylabel  ← ax.get_ylabel()
             series  ← legend handles → 反查 Palette.get_color_name()
             chart_type ← 标记为 "unknown"
             summary ← ""
```

**字体校验**:
```python
def _validate_fonts(self) -> list[str]:
    for fig in plt.get_fignums():
        for artist in plt.figure(fig).findobj(match=Text):
            fp = artist.get_fontproperties()
            if fp is None or fp.get_family() == ["sans-serif"]:
                warnings.append(f"⚠️ '{artist.get_text()[:30]}' 未设置 FontProperties")
```

### 2.5 ChartTheme (`chart_theme.py`)

重构为：
- `initialize()` 委托 `FontManager.initialize()`，不再设置 rcParams 字体
- 保留 DPI/figsize/grid/linewidth/fontsize 等样式设置
- 移除 `_find_chinese_font()` 函数

### 2.6 ChartService (`chart_service.py`)

```python
def render(self, code: str) -> dict:
    result = self._renderer.render(code, output_path)
    png_url = self._storage.upload(result.image_path)

    # 上传 metadata.json
    json_path = self._get_metadata_path(result.image_path)
    metadata_url = self._storage.upload(json_path)

    # SSE: image.uploaded (现有)
    # SSE: chart.metadata (新增)
    return {
        "type": "image",
        "url": png_url,
        "metadata": result.metadata.to_dict(),
        "metadata_url": metadata_url,
        "summary": result.summary,
    }
```

## 3. Prompt 改造

### 3.1 Chart Code Prompt (`_CHART_CODE_PROMPT`)

新增规则：
- 使用 `cn_font` 变量（已注入到 exec 上下文）
- 所有文本 API 必须传入 `fontproperties=cn_font`
- 用 `palette.Palette.get_series_colors(N)` 获取颜色
- 必须设置 `__chart_metadata__`:
  ```python
  __chart_metadata__ = {
      "chart_type": "bar",
      "title": "GDP增长率",
      "series": [
          {"name": "GDP", "color": "#2F80ED", "color_name": "蓝色"},
          {"name": "CPI", "color": "#27AE60", "color_name": "绿色"},
      ],
      "summary": "GDP在2020-2024年间稳定增长",
  }
  ```
- 禁止 `plt.rcParams['font.sans-serif']` 设置

### 3.2 Composer Prompt (`_build_composer_system_prompt`)

- 接收 ChartResult 列表，以 `to_markdown_hint()` 格式传递
- 颜色描述引用 `series[].color_name`，格式: `系列名（颜色名）`
- 图表摘要引用 `summary`
- 禁止自行描述图表颜色

### 3.3 Data Analyst Prompt (DB seed)

- 新增: "颜色描述必须来自 Chart Metadata，不得根据图片推测"
- 新增: "引用图例格式: 系列名（颜色名），颜色信息来自图表元数据"
- 新增: "使用 ChartResult.summary 作为图表描述，不要自行解释图表"

## 4. SSE 协议

### 4.1 image.uploaded (现有，不变)
```json
{"type": "image.uploaded", "url": "...", "filename": "chart_abc.png"}
```

### 4.2 chart.metadata (新增)
```json
{
  "type": "chart.metadata",
  "image_url": "...",
  "metadata": {
    "title": "GDP增长率",
    "chart_type": "bar",
    "xlabel": "年份",
    "ylabel": "增长率(%)",
    "series": [
      {"name": "GDP", "color": "#2F80ED", "color_name": "蓝色"},
      {"name": "CPI", "color": "#27AE60", "color_name": "绿色"}
    ]
  },
  "summary": "GDP在2020-2024年间稳定增长",
  "metadata_url": "..."
}
```

## 5. 最终文件结构

```
ai_service/chart/
├── __init__.py
├── font_manager.py          # ✨ NEW: FontManager
├── palette.py               # ✨ NEW: Palette + PaletteColor
├── chart_result.py          # ✨ NEW: ChartResult + ChartMetadata + SeriesInfo
├── chart_theme.py           # 🔧 重构: 委托 FontManager
├── chart_renderer.py        # 不变: AbstractChartRenderer
├── chart_service.py         # 🔧 重构: ChartResult, metadata SSE
├── minio_storage.py         # 不变
├── renderers/
│   ├── __init__.py
│   └── matplotlib_renderer.py  # 🔧 重构: 变量桥接 + 降级 + 校验
└── utils/
    ├── __init__.py
    └── color_utils.py       # 🔧 委托 Palette, 向后兼容
```
