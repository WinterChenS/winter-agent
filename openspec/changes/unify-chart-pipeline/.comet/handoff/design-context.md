# Comet Design Handoff

- Change: unify-chart-pipeline
- Phase: design
- Mode: compact
- Context hash: 317b773afcc23150c11094d48557e3b0c09a07b4fa6e4496298ce1405c8aab00

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/unify-chart-pipeline/proposal.md

- Source: openspec/changes/unify-chart-pipeline/proposal.md
- Lines: 1-34
- SHA256: 176b8da22cf4a3181124f3fbca98e24cbff137f0d904bc4f639a3d145f16a79f

```md
## Why

当前系统存在两套图表生成方案：ECharts option（前端渲染）和 matplotlib PNG（Python 端渲染）。这导致 Agent 行为不一致、前端需要判断不同数据结构、Prompt 难以约束、维护成本高。必须彻底统一为唯一的图表生成路径：matplotlib → PNG → MinIO → image URL → React `<img>`。

## What Changes

- **BREAKING**: 删除 ECharts 前端渲染路径，移除 `echarts-for-react` 依赖和所有 ECharts 组件
- **BREAKING**: 删除 Python `_extract_charts` 逻辑和 `chart_spec` SSE 事件类型
- 新建 `ai_service/chart/` 企业级模块：ChartService、ChartTheme、MatplotlibRenderer、MinioStorage
- 统一图表主题：微软雅黑、1600×900、DPI 200+、白色背景、浅灰网格、商务风格
- 所有 matplotlib 图表强制中文标签（标题/坐标轴/图例）
- CodeSandboxTool 移除 matplotlib preamble，改为调用 ChartService
- 更新 Agent system_prompt（DB）：禁止输出 ECharts option，只允许使用 execute_python 生成图表
- 前端 MessageBubble 移除 ECharts 渲染，`[CHART:n]` 标记处理，chart_spec 数据卡片
- 前端只保留 `image.uploaded` SSE 事件的 `<img>` 渲染
- Spring Boot 新增 ImageMessage 类型

## Capabilities

### New Capabilities
- `chart-service`: 统一图表生成服务入口，支持 matplotlib 渲染引擎，预留 Seaborn/Plotly 扩展点
- `chart-theme`: 企业级图表主题配置（字体、颜色、布局、DPI）
- `image-message-protocol`: 统一图片消息协议（type: image, url, width, height, title）

### Modified Capabilities
<!-- 本次不修改已有 spec -->

## Impact

- **Python**: 新增 `chart/` 模块（~6 files）；删除 `_extract_chars`、`chart_spec` 逻辑；修改 CodeSandboxTool preamble
- **前端**: 删除 `echarts-for-react` 依赖；MessageBubble 移除 ECharts/ChartSpec 渲染；ChartRenderer/BlockRenderer 标记 @deprecated
- **DB**: 更新 agent_definitions 的 system_prompt 字段
- **Spring Boot**: 新增 ImageMessage.java
- **依赖**: 前端移除 echarts、echarts-for-react；Python 无新依赖
```

## openspec/changes/unify-chart-pipeline/design.md

- Source: openspec/changes/unify-chart-pipeline/design.md
- Lines: 1-100
- SHA256: 480be0bf52edc0da97f090b554fac6a0014faa0d37df664b03ca23c665cd4d63

[TRUNCATED]

```md
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
```

Full source: openspec/changes/unify-chart-pipeline/design.md

## openspec/changes/unify-chart-pipeline/tasks.md

- Source: openspec/changes/unify-chart-pipeline/tasks.md
- Lines: 1-54
- SHA256: 25500463cb7c4ba60d27ba0f2adf7ecc06d1b6a9435b09cbcd98e84d9d90a132

```md
## 1. Python — Chart 模块搭建

- [ ] 1.1 创建 `chart/` 目录结构和 `__init__.py`
- [ ] 1.2 实现 `chart/chart_theme.py`：ChartTheme.initialize() 统一字体/颜色/DPI/尺寸配置
- [ ] 1.3 实现 `chart/utils/color_utils.py`：企业配色方案（主色/辅色/强调色）
- [ ] 1.4 实现 `chart/chart_renderer.py`：AbstractChartRenderer 抽象基类
- [ ] 1.5 实现 `chart/renderers/matplotlib_renderer.py`：MatplotlibRenderer 继承 AbstractChartRenderer
- [ ] 1.6 实现 `chart/minio_storage.py`：MinioStorage.upload() 封装（生成临时文件→上传→删除）
- [ ] 1.7 实现 `chart/chart_service.py`：ChartService.render(code) 统一入口

## 2. Python — 删除 ECharts 路径

- [ ] 2.1 删除 `CollaborationEngine._extract_charts()` 方法
- [ ] 2.2 删除 `CollaborationEngine.execute()` 中的 chart_keywords 检测和 chart_specs 赋值
- [ ] 2.3 删除 `graph/multi_agent_graph.py` 中 collaboration 返回值的 `chart_specs` 字段
- [ ] 2.4 删除 `api/routes/chat.py` 中的 chart_specs 提取和 chart SSE 事件发送
- [ ] 2.5 删除 `domain/event_envelope.py` 中 `envelope_chart` 函数的 `message_id` 参数（恢复简洁版）
- [ ] 2.6 更新 `answer_node` prompt：移除 `[CHART:n]` 引用和 "Available Charts" section

## 3. Python — CodeSandboxTool 简化

- [ ] 3.1 修改 `_build_preamble()`：移除 matplotlib 字体配置代码，改为注入 `from chart.chart_theme import ChartTheme; ChartTheme.initialize()`
- [ ] 3.2 验证 execute_python 工具生成图表后中文字体正常

## 4. Python — Agent Prompt 更新（DB）

- [ ] 4.1 更新 seed SQL：所有 agent system_prompt 增加「禁止输出 ECharts option，只用 execute_python 画图」规则
- [ ] 4.2 运行迁移脚本更新 DB

## 5. 前端 — 删除 ECharts

- [ ] 5.1 `npm uninstall echarts echarts-for-react`
- [ ] 5.2 删除 `MessageBubble.tsx` 中的 `ReactECharts` import 和 `chartSpecToOption()` 函数
- [ ] 5.3 删除 `MessageBubble.tsx` 中的 `[CHART:n]` 解析和 chart 渲染代码块
- [ ] 5.4 删除 `chatApi.ts` 中的 `chart` SSE 事件处理
- [ ] 5.5 删除 `chatStore.ts` 中的 `addChart` 和 `charts` 相关代码
- [ ] 5.6 删除 `types/chat.ts` 中的 `charts` 字段
- [ ] 5.7 简化 `MessageBubble.tsx` 只保留 `image.uploaded` 的 `<img>` 渲染

## 6. 前端 — 图片展示增强

- [ ] 6.1 MessageBubble 中的 `<img>` 添加点击预览（弹窗大图）
- [ ] 6.2 添加下载按钮

## 7. Spring Boot

- [ ] 7.1 新增 `ImageMessage.java` 类型（type, title, url, width, height）

## 8. 测试与验证

- [ ] 8.1 运行 Python 测试套件，确认无回归
- [ ] 8.2 运行前端 TypeScript 编译，确认无 ECharts 引用错误
- [ ] 8.3 E2E 测试：发送"画折线图" → 验证只返回 image URL，无 ECharts option
- [ ] 8.4 验收检查：确认整个系统只有一种图表方案
```

