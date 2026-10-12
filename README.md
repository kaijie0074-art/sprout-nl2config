# sprout-nl2config（缺陷基线 v0.1.0）

> ⚠️ 这是**缺陷基线快照**：LLM 裸输出 JSON 直接当配置结果的 naive 管线。用于复现问题报告的全部失败模式，不应用于任何真实场景。

## 现状

- `nl2config/api.py`：一次生成、裸输出直返、无校验、无重试、无降级；patch 盲目应用（无白名单/无锁/允许整树替换）。
- `nl2config/validators.py`：校验代码存在（平台侧散落逻辑的整理稿），但**管线没有调用**——这正是问题报告的核心发现。

## 复现

```bash
python3 -m unittest discover -s tests
# Ran 21 tests ... FAILED (failures=26)
```

失败清单与失败模式的对位见主仓库 `docs/02-复现材料.md`；修复版见 [sprout-nl2config](../sprout-nl2config)（v1.0.0，21/21 通过）。
