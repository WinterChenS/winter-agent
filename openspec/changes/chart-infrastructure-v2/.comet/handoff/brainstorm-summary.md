# Brainstorm Summary

- Change: chart-infrastructure-v2
- Date: 2026-06-28

## 确认的技术方案

### Metadata 提取策略：变量桥接 + 两层降级
- L1: LLM 在代码中设置 `__chart_metadata__` dict（chart_type/title/series/summary），完整 dict 协议
- L2: 缺失字段从 matplotlib figure state 自动提取（title/xlabel/ylabel 从 axes，series 从 legend handles）
- L3: 都拿不到则留空/unknown

### 前端协议：新 SSE 事件 `chart.metadata`
- 新增独立 `chart.metadata` SSE 事件推送 metadata JSON
- `image.uploaded` 保持不变
- 旧前端忽略新事件，不破坏兼容性

### 字体校验：Prompt + 运行时检测
- Prompt 明确要求所有文本 API 使用 `fontproperties=cn_font`
- exec 后扫描 figure 中所有 Text Artist，fontproperties 为默认值的记录 WARNING
- 同时注入 `cn_font` 变量到 exec context

### 数据流架构
```
LLM Code (Prompt 要求 __chart_metadata__ + cn_font)
  → MatplotlibRenderer.render() 
    → FontManager.get_cn_font() 注入
    → exec(code, ctx)
    → 两层降级提取 metadata
    → 字体合规扫描
    → PNG + metadata.json
    → ChartResult
  → ChartService → MinIO + SSE (image.uploaded + chart.metadata)
  → Composer → Markdown 引用 metadata
```

### 模块结构
- font_manager.py: FontManager (模块级单例, 幂等初始化, 跨平台字体发现, CHART_FONT_PATH 环境变量)
- palette.py: Palette + PaletteColor (8+4 企业色板, get_series_colors(n) 超限色相扩展, get_color_name(hex))
- chart_result.py: ChartResult + ChartMetadata + SeriesInfo (to_dict/to_markdown_hint)
- matplotlib_renderer.py: 重构 render() 注入 cn_font + 变量桥接 + 降级 + 字体校验
- chart_theme.py: 委托 FontManager, 保留非字体配置
- chart_service.py: 适配 ChartResult, 新增 metadata SSE

## 关键取舍与风险

| 取舍 | 选择 | 理由 |
|------|------|------|
| 变量桥接 vs 自动提取 | 桥接 + 降级 | 可靠性优先，降级兜底 |
| 新 SSE vs 扩展现有 | 新事件 | 协议清晰，不破坏旧字段 |
| Runtime 检测 vs Prompt only | 两者结合 | Prompt 预防，检测兜底 |
| 完整 dict vs 最小字段 | 完整 dict | LLM 必须声明颜色映射保证一致性 |

## 测试策略

- FontManager: 单元测试(字体发现/缓存/fallback/幂等)
- Palette: 单元测试(颜色名查询/序列色/超限扩展)
- ChartRenderer: 单元测试(ChartResult 返回/L1/L2 降级/字体校验)
- 端到端: 线图/柱状图/饼图/散点图/直方图/箱线图/热力图 中文验证 + metadata 正确性
- 回归: 运行现有 test_chart_generator.py, test_chart_validators.py, test_data_analyst.py

## Spec Patch

无（现有 specs 已充分覆盖设计决策）
