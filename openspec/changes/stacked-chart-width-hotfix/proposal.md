# stacked-chart-width-hotfix

## 问题

绘制堆积图时，生成的图表代码可能会把 `width` 作为关键字参数传给 `ChartSpec(...)`，运行时触发：

```text
TypeError: ChartSpec.__init__() got an unexpected keyword argument 'width'
```

## 根因

- `ai_service/chart/chart_spec.py` 中的 `ChartSpec` 只接受 `figsize`，不接受 `width` / `height`
- 图表代码生成后的执行前校验只要求必须调用 `ChartSpec` 和 `render_from_spec`，没有拦截非法构造参数
- 因此错误代码会进入真实执行路径，在运行时才报错

## 修复目标

- 在执行前拦截 `ChartSpec(width=...)` / `ChartSpec(height=...)` 这类非法参数用法
- 给重试提供更明确的拒绝理由，促使模型改用合法的 `ChartSpec` API
- 为该场景补回归测试，避免再次在运行时暴露同类错误