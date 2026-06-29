# Brainstorm Summary

- Change: chart-single-source-truth
- Date: 2026-06-29

## 确认的技术方案

1. **ChartSpec 先行** — LLM 代码构建 ChartSpec → ChartRenderer.render_from_spec() 渲染 + 输出 metadata
2. **metadata.json 文件传递** — 跨越 subprocess 进程边界：ChartRenderer 保存 metadata.json，Tool 扫描读取
3. **Palette 7 语义常量** — PRIMARY/SECONDARY/SUCCESS/WARNING/ERROR/INFO/NEUTRAL，每个含 hex + name_cn
4. **FontManager** — FontProperties 缓存，get_cn_font() 自动初始化，跨平台字体发现
5. **Summary 自动计算** — 线性回归趋势 + 增长率，ChartRenderer 从 ChartSpec.all_values() 计算
6. **向后兼容** — ChartService 检测 __chart_spec__ 变量；有则 render_from_spec，无则 render(code, path)
7. **metadata 传递链路** — metadata.json → ToolResult.charts → execution_results → composer prompt → Markdown

## 关键取舍与风险

- **取舍**: ChartSpec 增加 LLM 代码结构约束 → 换来 metadata 100% 准确
- **风险**: LLM 不遵循 ChartSpec API → 降级到旧流程（无 metadata，功能不退化）
- **风险**: 中文字体 tofu → FontManager 覆盖主流 OS + fallback WARNING

## 测试策略

单元测试: Palette / FontManager / ChartSpec / ChartResult.compute_summary
集成测试: ChartRenderer.render_from_spec() 6 种图表类型 + Sandbox Tool metadata 扫描
端到端: 完整 LLM code → execute_python → metadata → composer prompt 链路
回归: 现有 test_chart_generator.py / test_data_analyst.py

## Spec Patch

无 — delta spec 已在 open 阶段对齐确认的设计方案
