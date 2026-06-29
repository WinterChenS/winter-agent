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

| 常量 | hex | colorName |
|------|-----|-----------|
| PRIMARY | #2F80ED | 蓝色 |
| SECONDARY | #27AE60 | 绿色 |
| SUCCESS | #219653 | 深绿 |
| WARNING | #F2994A | 橙色 |
| ERROR | #EB5757 | 红色 |
| INFO | #9B51E0 | 紫色 |
| NEUTRAL | #828282 | 灰色 |

扩展序列色：N 个 series 时按顺序取，超限时 HSL 色相微调。`Palette.get_color_name(hex)` 查表返回中文名，未知 hex 返回原值。

### 4. FontManager 设计

替代 `plt.rcParams['font.sans-serif']` 方案，使用 `fontproperties=` 参数覆盖所有 matplotlib Artist：

- 启动时扫描系统字体，缓存 FontProperties
- 跨平台：macOS (PingFang SC → Heiti SC)，Linux (Noto Sans CJK SC)，Windows (Microsoft YaHei)
- 幂等初始化，无中文字体时 fallback + WARNING
- preamble 注入 `cn_font = FontManager.get_cn_font()` 变量

### 5. Summary 自动计算

ChartRenderer 从 ChartSpec 自动提取统计：

```python
def _compute_summary(spec: ChartSpec) -> str:
    # 从 series/slices/points 提取所有数值
    # 计算 max, min, avg, trend (斜率正负), growth_rate
    # 返回结构化文本，LLM 可直接引用
```

LLM 不需要编写 summary 计算代码。

### 6. 兼容性

- `MatplotlibRenderer.render(code, output_path)` 签名不变，仍然返回 `str` (path)
- 新增 `MatplotlibRenderer.render_from_spec(spec, output_path)` 返回 `ChartResult`
- `ChartService.render()` 检测 LLM 代码是否构建了 ChartSpec（通过 `__chart_spec__` 变量），有则走 render_from_spec，无则走原流程
- execute_python ToolResult 增加可选的 `metadata` 字段，非图表代码不受影响

### 7. Prompt 变更范围

- **chart code prompt** (`_CHART_CODE_PROMPT`): 要求使用 ChartSpec + Palette + FontManager，禁止 rcParams
- **composer prompt** (`_build_composer_system_prompt`): 传递 metadata + summary，要求引用禁止推测
- **Data Analyst system prompt** (DB seed): 添加 metadata 引用规则

## Risks / Trade-offs

- [Risk] LLM 不遵循 ChartSpec API → 旧代码仍然工作（fallback to render(code, path)），只是没有 metadata 保护
- [Risk] ChartSpec 无法覆盖所有 matplotlib 用法 → 只覆盖 6 种核心图表类型，复杂图保持原流程
- [Trade-off] ChartSpec 增加 LLM 代码结构约束 → 换来 metadata 100% 准确
