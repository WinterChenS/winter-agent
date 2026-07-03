# sandbox-scipy-hotfix

## 问题

图表绘制通过 `execute_python` 沙箱执行生成代码时，运行期可能出现：

```text
ModuleNotFoundError: No module named 'scipy'
```

当前项目 Python 运行环境未安装 `scipy`，导致一旦生成代码或数据处理逻辑依赖该库，图表执行会直接失败。

## 根因

- `ai_service/.venv` 中无法导入 `scipy`
- `ai_service/requirements.txt` 未声明 `scipy`
- 沙箱执行路径会直接使用该环境运行 Python 代码，因此缺失会在真实请求中暴露

## 修复目标

- 为 AI service 运行环境补齐 `scipy` 依赖
- 增加回归测试，确保沙箱可以成功导入 `scipy`
- 不修改图表协议、接口或执行流程