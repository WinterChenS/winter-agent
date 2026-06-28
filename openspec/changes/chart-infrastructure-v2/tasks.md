## 1. FontManager — 统一字体管理

- [x] 1.1 创建 `ai_service/chart/font_manager.py`：FontManager 类，`initialize()` 扫描并缓存 FontProperties，`get_cn_font()` 返回缓存实例
- [x] 1.2 实现跨平台字体发现：macOS (PingFang SC → Heiti SC → STHeiti → Arial Unicode MS)，Windows (Microsoft YaHei → SimHei → KaiTi)，Linux (Noto Sans CJK SC → Noto Sans SC → WenQuanYi Micro Hei)
- [x] 1.3 FontManager 幂等初始化：多次调用 `initialize()` 只扫描一次，日志记录选中字体
- [x] 1.4 Fallback 策略：无中文字体时返回默认 FontProperties + WARNING 日志

## 2. Palette — 企业调色板

- [x] 2.1 创建 `ai_service/chart/palette.py`：PaletteColor NamedTuple (hex + name_cn)，Palette 类包含 PRIMARY/SECONDARY/SUCCESS/WARNING/ERROR/INFO/NEUTRAL 常量
- [x] 2.2 实现 `Palette.get_series_colors(n)` — 返回 n 个 PaletteColor，超限时循环+色相微调
- [x] 2.3 实现 `Palette.get_color_name(hex)` — hex 到中文颜色名查询，未知 hex 返回自身
- [x] 2.4 替换 `ai_service/chart/utils/color_utils.py` 中的旧 PALETTE，保持向后兼容导出

## 3. ChartResult + ChartMetadata — 统一数据结构

- [x] 3.1 创建 `ai_service/chart/chart_result.py`：ChartResult(image_path, metadata, summary) 和 ChartMetadata(title, chart_type, xlabel, ylabel, series) 数据类
- [x] 3.2 ChartMetadata.to_json() 序列化方法，ChartMetadata.to_markdown_hint() 生成 LLM 可引用的文本片段
- [x] 3.3 SeriesInfo 数据类：name + color(hex) + color_name(中文)

## 4. ChartRenderer 重构

- [x] 4.1 重构 `MatplotlibRenderer.render()` 返回 ChartResult 替代 str
- [x] 4.2 exec 上下文注入 `cn_font` 变量（FontManager.get_cn_font()）
- [x] 4.3 从 matplotlib figure state 提取 metadata（title/xlabel/ylabel/legend/series）
- [x] 4.4 支持 `__chart_result_summary__` 用户变量注入 summary，或自动生成模板化 summary
- [x] 4.5 确保 `ChartResult.image_path` 与旧返回值兼容

## 5. Metadata JSON 输出

- [x] 5.1 ChartRenderer 在保存 PNG 的同时输出 `{basename}_metadata.json`
- [x] 5.2 修改 `ChartService.render()` 返回包含 metadata 的响应
- [x] 5.3 ChartService 返回格式更新：`{"type":"image","url":...,"metadata":{...},"summary":"..."}`

## 6. ChartTheme 适配

- [x] 6.1 重构 `ChartTheme.initialize()` 委托 FontManager 初始化，移除 rcParams 字体设置
- [x] 6.2 ChartTheme 保留 DPI/figsize/grid/fontsize 等非字体配置

## 7. Sandbox Tool 适配

- [x] 7.1 修改 `CodeSandboxTool._build_preamble()` 注入 `from chart.font_manager import FontManager; cn_font = FontManager.get_cn_font()`
- [x] 7.2 preamble 注入 `from chart.palette import Palette` 和 Palette 色板变量
- [x] 7.3 移除 preamble 中仅依赖 rcParams 的 `ChartTheme.initialize()` 调用（或改为仅设置非字体样式）

## 8. Prompt 更新

- [x] 8.1 更新 `_CHART_CODE_PROMPT`（nodes.py）：要求所有文本 API 使用 `fontproperties=cn_font`，禁止 `plt.rcParams['font.sans-serif']`，从 Palette 取色，设置 summary
- [x] 8.2 更新 Composer prompt（`_build_composer_system_prompt`）：传递 ChartResult 列表，要求引用 metadata 颜色描述，禁止自行推测颜色
- [x] 8.3 更新 Data Analyst Agent system prompt（DB seed）：添加"颜色描述必须来自 Chart Metadata"规则，添加"引用图例格式：系列名（颜色名）"规则

## 9. 清理与测试

- [x] 9.1 删除旧 `_find_chinese_font()` 函数（chart_theme.py），全部委托 FontManager
- [x] 9.2 运行现有测试确认无回归（`test_chart_generator.py`, `test_chart_validators.py`, `test_data_analyst.py`）
- [x] 9.3 新增 FontManager 单元测试：字体发现、缓存、fallback
- [x] 9.4 新增 Palette 单元测试：颜色名查询、序列色获取、超限处理
- [x] 9.5 新增 ChartRenderer 单元测试：ChartResult 返回、metadata 提取
- [x] 9.6 端到端验证：生成线图/柱状图/饼图/散点图/直方图/热力图，确认中文正常、metadata 正确
