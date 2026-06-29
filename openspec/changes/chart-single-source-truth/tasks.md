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
