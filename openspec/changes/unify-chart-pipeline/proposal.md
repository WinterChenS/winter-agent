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
