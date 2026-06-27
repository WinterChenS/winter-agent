## Context

当前系统有两套图表实现：(1) CollaborationEngine._extract_charts → chart_spec → chart SSE → 前端 ECharts 渲染；(2) execute_python 工具内 matplotlib → PNG 文件 → MinIO 上传。方案 (1) 依赖 LLM 提取 JSON 数据并输出 `[CHART:n]` 标记，方案 (2) 依赖 LLM 写 Python 代码。两套方案导致前端需要处理两种数据结构，Agent prompt 难以统一。

## Goals / Non-Goals

**Goals:**
- 统一为唯一图表生成路径：matplotlib → PNG → MinIO → image URL → React `<img>`
- 新建企业级 `chart/` 模块，支持 matplotlib 当前，预留 Seaborn/Plotly 扩展
- 删除所有 ECharts 前端代码和 `_extract_charts` Python 代码
- Agent prompt 强制只使用 execute_python 生成图表

**Non-Goals:**
- 不改 MinIO 基础设施
- 不改 SSE 协议框架
- 不改 Agent 路由/Collaboration 核心流程

## Decisions

### 1. Chart 模块架构

```
chart/
├── __init__.py
├── chart_service.py      # 统一入口：ChartService.render(code) → image_url
├── chart_theme.py         # 主题：字体/颜色/网格/DPI/尺寸
├── chart_renderer.py      # 抽象基类 AbstractChartRenderer
├── minio_storage.py       # MinIO 上传封装
├── renderers/
│   ├── __init__.py
│   └── matplotlib_renderer.py  # MatplotlibRenderer 实现
└── utils/
    ├── __init__.py
    └── color_utils.py     # 企业配色方案
```

**ChartService** 是唯一对外接口：
```python
class ChartService:
    def render(self, code: str) -> dict:
        # 1. 执行 Python 代码生成图片
        # 2. 上传 MinIO
        # 3. 返回 {"type": "image", "url": "...", "width": 1600, "height": 900}
```

**ChartTheme** 统一初始化：
```python
class ChartTheme:
    @staticmethod
    def initialize():
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", ...]
        plt.rcParams["axes.unicode_minus"] = False
        plt.rcParams["figure.dpi"] = 200
        plt.rcParams["figure.figsize"] = (16, 9)
        plt.rcParams["axes.grid"] = True
        plt.rcParams["grid.alpha"] = 0.3
```

### 2. 删除 ECharts 路径

- 前端：删除 `echarts-for-react` import，删除 `chartSpecToOption()`，删除 `ReactECharts` 渲染，删除 `[CHART:n]` 解析
- Python：删除 `CollaborationEngine._extract_charts`，删除 `chart` SSE 事件类型，删除 `answer_node` prompt 中的 `[CHART:n]` 引用
- DB：更新 agent system_prompt，删除与 chart/图表的 JSON option 输出相关指引

### 3. 前端只渲染 image.uploaded

MessageBubble 中图表相关代码简化为：
```tsx
{message.images && Object.entries(message.images).map(([filename, url]) => (
  <img src={url} alt={filename} className="max-w-full rounded cursor-pointer"
       onClick={() => openPreview(url)} />
))}
```

### 4. Agent Prompt 修改

更新 DB 中所有 agent 的 system_prompt，增加规则：
- "任何涉及数据分析/图表/可视化 → 只允许调用 execute_python 工具"
- "禁止输出 ECharts option、JSON 图表数据"
- "matplotlib 会自动使用中文和商务主题，无需手动配置字体"

### 5. 代码沙箱 preamble 简化

CodeSandboxTool 的 `_build_preamble()` 不再注入 matplotlib 字体配置（ChartTheme 已统一处理），改为注入 `from chart.chart_theme import ChartTheme; ChartTheme.initialize()`。

## Data Flow

```
用户 "画折线图" → Agent 决定调 execute_python
→ LLM 写 matplotlib 代码（plt.savefig("chart.png")）
→ ChartService.render(code)
  → ChartTheme.initialize() + 执行代码
  → 生成 chart.png
  → MinioStorage.upload("chart.png")
  → 删除本地文件
  → 返回 {"type": "image", "url": "https://minio/xxx.png", "width": 1600, "height": 900}
→ tool result: "图表已生成: https://minio/xxx.png"
→ CollaborationEngine._scan_and_upload_images 扫描输出 → 已有 MinIO URL，无需二次上传
→ image.uploaded SSE 事件 → 前端 store.addImage → MessageBubble 渲染 <img>
```
