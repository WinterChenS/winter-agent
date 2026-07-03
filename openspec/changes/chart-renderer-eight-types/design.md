# chart-renderer-eight-types 设计

## 实现说明

在现有 `TestRenderFromSpec` 测试类中补齐缺失的 4 种图形：

- `area`
- `radar`
- `histogram`
- `heatmap`

每种图形只增加 1 个最小可渲染用例，统一断言：

- `render_from_spec()` 返回成功
- 输出 PNG 文件存在
- 必要时补一两个轻量 metadata 断言，避免测试过重

## 快速验证

使用单条命令完成回归：

```bash
cd /Volumes/work/projects/winter-agent/ai_service && PYTHONPATH=$PWD .venv/bin/python -m pytest tests/test_chart_renderer_v2.py -q
```