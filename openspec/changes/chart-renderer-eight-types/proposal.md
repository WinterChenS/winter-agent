# chart-renderer-eight-types

## 动机

当前 `MatplotlibRenderer.render_from_spec()` 已支持 8 种图形类型，但测试文件只覆盖了其中一部分，缺少对其余类型的最小可渲染回归用例。

## 目标

- 为当前支持的 8 种图形补齐最小可渲染测试
- 继续把测试收敛在 `ai_service/tests/test_chart_renderer_v2.py`
- 保持单条快速验证命令：`pytest test_chart_renderer_v2.py -q`

## 范围

- 仅补齐 renderer 单测
- 不修改 ChartSpec 协议
- 不改动渲染器实现，除非新增测试暴露真实缺陷