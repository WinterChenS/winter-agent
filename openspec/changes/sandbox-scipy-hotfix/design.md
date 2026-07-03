# sandbox-scipy-hotfix 设计

## 方案

采用最小修复：

1. 在 `ai_service/requirements.txt` 中新增 `scipy`
2. 在 `ai_service/tests/test_code_sandbox.py` 中增加一个失败用例，验证沙箱执行 `import scipy` 成功

## 为什么这样修

- 报错发生在沙箱实际运行环境，不是调用链或控制流问题
- 现有图表/分析沙箱已经内置 `pandas`、`numpy`、`matplotlib`，补齐 `scipy` 与该工具定位一致
- 改动范围小，不涉及架构、接口或 OpenSpec capability 变更

## 非目标

- 不改写图表生成 prompt
- 不新增新的图表能力
- 不调整沙箱执行模型