---
comet_change: chart-single-source-truth
role: technical-design
canonical_spec: openspec
---

# Chart Single Source of Truth — Technical Design

## 1. 数据流架构

```
LLM Code (subprocess)
  │
  ├── ChartSpec(title, chart_type, series=[SeriesSpec(...)], ...)
  ├── Palette.PRIMARY / SECONDARY / ... (固定 hex + name_cn)
  ├── cn_font = FontManager.get_cn_font() (FontProperties 缓存)
  │
  ▼
ChartRenderer.render_from_spec(spec, "chart_0.png")
  │
  ├── 渲染 matplotlib 图表 → chart_0.png
  ├── 保存 metadata.json (ChartSpec.to_metadata())
  ├── 自动 compute_summary(all_values)
  │
  ▼
ChartResult(image_path, metadata, summary, stdout)
  │
═══ process boundary ═══
  │
CodeSandboxTool.execute()
  ├── 扫描 *_metadata.json
  ├── 匹配 PNG URL
  └── ToolResult.charts = [{image, url, metadata, summary}]
  │
  ▼
graph execution_node → execution_results
  │
  ▼
composer_node._build_composer_system_prompt()
  ├── 每个 chart 附带 metadata + summary
  └── 规则: "颜色/数值来自 metadata，禁止推测"
  │
  ▼
Composer LLM → Markdown（引用 metadata）
```

## 2. 核心数据结构

### Palette (chart/palette.py)

```python
class PaletteColor(NamedTuple):
    hex: str       # "#2F80ED"
    name_cn: str   # "蓝色"

class Palette:
    PRIMARY   = PaletteColor("#2F80ED", "蓝色")
    SECONDARY = PaletteColor("#27AE60", "绿色")
    SUCCESS   = PaletteColor("#219653", "深绿")
    WARNING   = PaletteColor("#F2994A", "橙色")
    ERROR     = PaletteColor("#EB5757", "红色")
    INFO      = PaletteColor("#9B51E0", "紫色")
    NEUTRAL   = PaletteColor("#828282", "灰色")
    _SERIES   = [...]  # 12 个 PaletteColor

    @classmethod
    def get_series_colors(cls, n: int) -> list[PaletteColor]:
        """返回 n 个颜色，超限时 HSL 色相微调"""
    @classmethod
    def get_color_name(cls, hex_str: str) -> str:
        """hex → 中文名，未知返回自身"""
```

### ChartSpec (chart/chart_spec.py)

```python
@dataclass
class SeriesSpec:
    name: str; color: str; color_name: str; values: list[float]

@dataclass
class SliceSpec:
    label: str; value: float; color: str; color_name: str

@dataclass
class PointSpec:
    x: float; y: float; label: str | None = None

@dataclass
class ChartSpec:
    title: str
    chart_type: str       # line/bar/pie/scatter/histogram/heatmap
    xlabel: str | None = None
    ylabel: str | None = None
    figsize: tuple = (12, 6)
    series: list[SeriesSpec] | None = None   # bar/line
    slices: list[SliceSpec] | None = None    # pie
    points: list[PointSpec] | None = None    # scatter
    data: list[list[float]] | None = None    # histogram/heatmap
    labels: list[str] | None = None

    def __post_init__(self):
        # 自动填充 series color_name
        if self.series:
            for s in self.series:
                if not s.color_name:
                    s.color_name = Palette.get_color_name(s.color)

    def to_metadata(self) -> dict: ...
    def all_values(self) -> list[float]: ...
```

### ChartResult (chart/chart_result.py)

```python
@dataclass
class ChartResult:
    image_path: str
    metadata: dict       # ChartSpec.to_metadata()
    summary: str         # compute_summary(auto_values)
    stdout: str

    @staticmethod
    def compute_summary(values: list[float], labels=None) -> str:
        """max/min/avg/trend(线性回归)/growth_rate"""
```

## 3. ChartRenderer 实现

### render_from_spec(spec, output_path)

```python
def render_from_spec(self, spec: ChartSpec, output_path: str) -> ChartResult:
    cn_font = FontManager.get_cn_font()
    fig, ax = plt.subplots(figsize=spec.figsize)

    match spec.chart_type:
        case "bar":    self._render_bar(ax, spec, cn_font)
        case "line":   self._render_line(ax, spec, cn_font)
        case "pie":    self._render_pie(ax, spec, cn_font)
        case "scatter": self._render_scatter(ax, spec, cn_font)
        case "histogram": self._render_histogram(ax, spec, cn_font)
        case "heatmap": self._render_heatmap(ax, spec, cn_font)

    ax.set_title(spec.title, fontproperties=cn_font)
    ax.set_xlabel(spec.xlabel, fontproperties=cn_font) if spec.xlabel else ...
    ax.set_ylabel(spec.ylabel, fontproperties=cn_font) if spec.ylabel else ...
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")

    # metadata
    metadata = spec.to_metadata()
    meta_path = output_path.replace(".png", "_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, ensure_ascii=False)

    summary = ChartResult.compute_summary(spec.all_values(), spec.labels)
    return ChartResult(output_path, metadata, summary, "")
```

### 各图表类型渲染策略

- **bar/line**: 遍历 spec.series，series.color 直接作为颜色
- **pie**: 遍历 spec.slices，slices[i].color 作为扇区颜色，autopct 显示百分比
- **scatter**: 遍历 spec.points，x/y 坐标散点
- **histogram**: spec.data[0] 作为原始数据，plt.hist 分箱
- **heatmap**: spec.data 作为二维数组，plt.imshow + colorbar

### render(code, path) — 向后兼容

保持现有 exec(code, ctx) 流程，返回 `ChartResult(path, {}, "", "")`。

## 4. metadata 传递链路

### 4.1 Sandbox Tool (tools/sandbox/tool.py)

```python
# _build_preamble() 新增注入:
from chart.font_manager import FontManager
cn_font = FontManager.get_cn_font()
from chart.palette import Palette
from chart.chart_spec import ChartSpec, SeriesSpec
from chart.renderers.matplotlib_renderer import MatplotlibRenderer

# execute() 新增 metadata 扫描:
charts = []
for f in os.listdir(cwd):
    if f.endswith('_metadata.json'):
        with open(os.path.join(cwd, f)) as mf:
            metadata = json.load(mf)
        image_name = f.replace('_metadata.json', '.png')
        url = uploaded.get(image_name, '')
        summary = metadata.pop('_summary', '')
        charts.append({"image": image_name, "url": url,
                       "metadata": metadata, "summary": summary})

return ToolResult.success({
    "output": ...,
    "images": uploaded,
    "charts": charts,  # 新增字段
})
```

### 4.2 Graph Nodes (graph/nodes.py)

execution_node 直接透传 ToolResult。composer_node._build_composer_system_prompt() 修改：

```python
def _format_artifacts(artifacts_list, charts_meta):
    """每个 chart 附带 metadata + summary"""
    for chart in charts_meta:
        meta = chart.get("metadata", {})
        series_desc = ", ".join(
            f'{s["name"]}（{s["color_name"]}）'
            for s in meta.get("series", [])
        )
        summary = chart.get("summary", "")
        lines.append(
            f"- [{aid}] CHART: {meta.get('title','')} ({meta.get('chart_type','')})\n"
            f"  Series: {series_desc}\n"
            f"  Summary: {summary}\n"
            f"  Image: ![{meta.get('title','')}]({chart['url']})\n"
            f"  CRITICAL: 颜色来自 series color_name，数值来自 summary，禁止推测"
        )
```

### 4.3 Prompts

**_CHART_CODE_PROMPT 改为：**
```
CRITICAL RULES:
1. Build ChartSpec with chart_type, title, series/slices/points
2. Use Palette.PRIMARY/SECONDARY/etc for colors (NOT random)
3. Use fontproperties=cn_font for ALL text; NEVER use plt.rcParams
4. Call MatplotlibRenderer().render_from_spec(spec, "chart_0.png")
5. Output ONLY valid Python code — no markdown, no explanation
```

**_build_composer_system_prompt 增加：**
```
- CRITICAL: 颜色描述必须来自 chart metadata 的 series color_name（如"GDP（蓝色）"）
- CRITICAL: 数值/趋势必须来自 chart summary，禁止从图片推测
- CRITICAL: 不包含 metadata 的 chart 不进行任何颜色/数值描述
```

## 5. FontManager (chart/font_manager.py)

```python
class FontManager:
    _initialized = False
    _cn_font: FontProperties | None = None

    _FONT_CANDIDATES = {
        "darwin": ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS"],
        "win32":  ["Microsoft YaHei", "SimHei", "KaiTi"],
        "linux":  ["Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei"],
    }

    @classmethod
    def get_cn_font(cls) -> FontProperties:
        if not cls._initialized:
            cls.initialize()
        return cls._cn_font

    @classmethod
    def initialize(cls):
        if cls._initialized: return
        cls._initialized = True
        for font_name in cls._FONT_CANDIDATES.get(sys.platform, []):
            if font_manager.findfont(font_name, fallback_to_default=False) != ...:
                cls._cn_font = FontProperties(fname=...)
                logger.info("FontManager: using %s", font_name)
                return
        cls._cn_font = FontProperties()
        logger.warning("FontManager: no CJK font found")
```

## 6. ChartTheme 适配

```python
class ChartTheme:
    @staticmethod
    def initialize():
        # 委托字体管理给 FontManager（幂等，多模块安全）
        FontManager.initialize()
        # 仅设置非字体样式
        plt.rcParams.update({
            "figure.dpi": 200,
            "figure.figsize": (16, 9),
            "axes.grid": True,
            "font.size": 12,
        })
```

## 7. 兼容性一览

| 场景 | render(code, path) | render_from_spec(spec, path) |
|------|-------------------|------------------------------|
| 旧代码（plt.bar + rcParams） | ✓ metadata 为空 | N/A |
| ChartSpec 新代码 | N/A | ✓ metadata 完整 |
| LLM 不遵循 ChartSpec | ✓ 降级，无 metadata | N/A |
| 非图表代码（数据分析） | ✓ 不受影响 | N/A |
