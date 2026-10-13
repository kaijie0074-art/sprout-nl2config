# 真实 LLM golden 回归实跑记录 · 2026-10-13

## 环境

- 端点：`https://open.bigmodel.cn/api/coding/paas/v4`（智谱 GLM Coding Plan，OpenAI 兼容）
- 凭证：环境变量注入，不入库
- 命令：`python3 -m nl2config.cli regress`（等价于下方脚本入口 `run_golden_regression`）

## 实跑结果（同日两轮，模型 glm-4-flash）

| 轮次 | 通过 | converged_rate | first_pass_rate | hallucination_rate | 失败对 |
|---|---|---|---|---|---|
| 第 1 轮 | 5/8 | 0.625 | — | 0.0 | 06 / 07 / 08 |
| 第 2 轮（落盘 JSON） | 3/8 | 0.375 | 0.25 | 0.0 | 01 / 02 / 03 / 07 / 08 |

逐对明细（第 2 轮，见 `live-llm-golden-20261013.json`）：

| golden 对 | 结果 | 尝试次数 |
|---|---|---|
| 01-video-info-site | ✗ | 4 |
| 02-ecommerce-live | ✗ | 4 |
| 03-community-ios | ✗ | 4 |
| 04-hallucination-repair | ✓ | 2 |
| 05-type-drift-repair | ✓ | 1 |
| 06-naming-drift-repair | ✓ | 1 |
| 07-missing-required-repair | ✗ | 4 |
| 08-platform-support-repair | ✗ | 4 |

## 解读（如实记录，不粉饰）

1. **幻觉率为 0**：两轮 16 次全过程中 `INVALID_COMPONENT_ID`（编造组件）零出现——注册表+合法枚举注入这层防线在真实模型上成立。
2. **收敛率不稳定（0.375–0.625）**：同模型同配置两轮失败集不同（第 1 轮 01-03 过而第 2 轮败，06 两轮相反）——真实 LLM 输出非确定性 + 结构违规在 3 次反馈重试内未必收敛。degraded 降级转人工按设计生效（永不返回非法配置）。
3. **glm-5.3-flash 无法完成**：reasoning 输出时长超过 `llm.py` 内置 60s HTTP 超时（实测中断），强模型在该管线里需先调大超时——记录为已知边界。
4. 本 golden 指标此前从未对真实模型在线度量过（fixture 时代表现 100%）；真实模型下"收敛率"是管线质量的真实刻度，改进方向：错误反馈模板针对结构化重试再强化（借鉴 instructor 差异化重试）。

## 离线回归不受影响

`python3 -m unittest discover -s tests`（ScriptedProvider 语料）全绿，CI 保持离线可跑。
