## 1. Python — Chart 模块搭建

- [x] 1.1 创建 `chart/` 目录结构和 `__init__.py`
- [x] 1.2 实现 `chart/chart_theme.py`：ChartTheme.initialize() 统一字体/颜色/DPI/尺寸配置
- [x] 1.3 实现 `chart/utils/color_utils.py`：企业配色方案（主色/辅色/强调色）
- [x] 1.4 实现 `chart/chart_renderer.py`：AbstractChartRenderer 抽象基类
- [x] 1.5 实现 `chart/renderers/matplotlib_renderer.py`：MatplotlibRenderer 继承 AbstractChartRenderer
- [x] 1.6 实现 `chart/minio_storage.py`：MinioStorage.upload() 封装（生成临时文件→上传→删除）
- [x] 1.7 实现 `chart/chart_service.py`：ChartService.render(code) 统一入口

## 2. Python — 删除 ECharts 路径

- [x] 2.1 删除 `CollaborationEngine._extract_charts()` 方法
- [x] 2.2 删除 `CollaborationEngine.execute()` 中的 chart_keywords 检测和 chart_specs 赋值
- [x] 2.3 删除 `graph/multi_agent_graph.py` 中 collaboration 返回值的 `chart_specs` 字段
- [x] 2.4 删除 `api/routes/chat.py` 中的 chart_specs 提取和 chart SSE 事件发送
- [x] 2.5 删除 `domain/event_envelope.py` 中 `envelope_chart` 函数的 `message_id` 参数（恢复简洁版）
- [x] 2.6 更新 `answer_node` prompt：移除 `[CHART:n]` 引用和 "Available Charts" section

## 3. Python — CodeSandboxTool 简化

- [x] 3.1 修改 `_build_preamble()`：移除 matplotlib 字体配置代码，改为注入 `from chart.chart_theme import ChartTheme; ChartTheme.initialize()`
- [x] 3.2 验证 execute_python 工具生成图表后中文字体正常

## 4. Python — Agent Prompt 更新（DB）

- [x] 4.1 更新 seed SQL：所有 agent system_prompt 增加「禁止输出 ECharts option，只用 execute_python 画图」规则
- [x] 4.2 运行迁移脚本更新 DB

## 5. 前端 — 删除 ECharts

- [x] 5.1 `npm uninstall echarts echarts-for-react`
- [x] 5.2 删除 `MessageBubble.tsx` 中的 `ReactECharts` import 和 `chartSpecToOption()` 函数
- [x] 5.3 删除 `MessageBubble.tsx` 中的 `[CHART:n]` 解析和 chart 渲染代码块
- [x] 5.4 删除 `chatApi.ts` 中的 `chart` SSE 事件处理
- [x] 5.5 删除 `chatStore.ts` 中的 `addChart` 和 `charts` 相关代码
- [x] 5.6 删除 `types/chat.ts` 中的 `charts` 字段
- [x] 5.7 简化 `MessageBubble.tsx` 只保留 `image.uploaded` 的 `<img>` 渲染

## 6. 前端 — 图片展示增强

- [x] 6.1 MessageBubble 中的 `<img>` 添加点击预览（弹窗大图）
- [x] 6.2 添加下载按钮

## 7. Spring Boot

- [x] 7.1 新增 `ImageMessage.java` 类型（type, title, url, width, height）

## 8. 测试与验证

- [x] 8.1 运行 Python 测试套件，确认无回归
- [x] 8.2 运行前端 TypeScript 编译，确认无 ECharts 引用错误
- [x] 8.3 E2E 测试：发送"画折线图" → 验证只返回 image URL，无 ECharts option
- [x] 8.4 验收检查：确认整个系统只有一种图表方案
