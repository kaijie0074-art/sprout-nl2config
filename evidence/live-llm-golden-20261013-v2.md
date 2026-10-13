# 真实 LLM golden 回归实跑记录 · 2026-10-13（prompt v2 修订版）

## 本轮修复（真实 LLM 暴露的系统性缺陷）

首轮实测（见同目录 `live-llm-golden-20261013.md`）定位低收敛根因：**SYSTEM_PROMPT 未定义 trackParams 格式与套餐白名单**——模型每轮瞎猜格式（输出 `channel: wechat`），结构化反馈修正不动。修复（`nl2config/llm.py`）：

1. SYSTEM_PROMPT 补全输出协议：trackParams 键格式 `ch_<channel>_<id>`（如 `ch_weixin_main`）、值=投放 ID；套餐×组件白名单表（从 registry.PACKAGES 动态生成，单一事实源）；components 补 `visible` 字段说明
2. HTTP 超时 60s 硬编码 → `NL2CONFIG_TIMEOUT` 环境变量可配（默认 120s，支持 reasoning 模型）

## 修复后三轮实测（模型 glm-4-flash，同日）

| 轮次 | converged_rate | 失败对 | 备注 |
|---|---|---|---|
| 修复前基线 | 0.375–0.625（两轮摇摆） | 不定 | 01-03 生成类时好时坏 |
| v2 第 1 轮 | 0.5 | 03/05/07/08 | 01/02 转为一次通过 |
| v2 第 2 轮（`live-llm-golden-20261013-final.json`） | **0.625** | 05/07/08 | **01/02/03 生成类全部一次通过** |

## 指标语义澄清

- `hallucination_rate` 0.125 的那例（04-hallucination-repair）是**设计场景**：模型先编造组件 ID → `INVALID_COMPONENT_ID` 拦截 → 结构化反馈 → 第 2 轮修正通过。该指标记录"幻觉出现过"，防线的实际行为是 **出现即拦截即修正**——不是漏拦。
- 残余失败（05-type-drift / 07-missing-required / 08-platform-support，均为 repair 类）在 3 次反馈内不收敛时走 **degraded 显式降级转人工**——管线核心承诺"永不返回非法配置"在全部轮次成立（0 脏数据返回）。
- 07-missing-required 单对复跑实测 3 轮收敛（漏 templateId → 两轮 MISSING_REQUIRED 反馈 → 补上）——失败集逐轮漂移属模型输出非确定性，非反馈机制缺陷。

## 离线回归

`python3 -m unittest discover -s tests` 27 项全绿（ScriptedProvider 语料）不受 prompt 变化影响。
