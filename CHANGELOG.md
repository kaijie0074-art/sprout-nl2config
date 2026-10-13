# 变更日志

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式。

## [research] - 2026-10-14

自主深潜研究（Q1–Q8 问题链，详见 [docs/research/deep-dive-20261014.md](docs/research/deep-dive-20261014.md)）。

### 新增
- **传输层韧性**：`OpenAICompatLLM` 429/5xx 退避重试（`NL2CONFIG_BACKOFF_SECONDS`/`NL2CONFIG_MAX_RETRIES`）与调用间隔（`NL2CONFIG_CALL_INTERVAL`），长实跑不再被共享配额限速打断。
- **研究开关**（默认全关，v2 基线逐字节不变）：反馈风格 `NL2CONFIG_FEEDBACK_STYLE=directive`（附加当前值+修正指令）、few-shot 注入 `NL2CONFIG_FEW_SHOT=1`。
- **降级现场保留**：`GenerationResult.last_raw_config`——降级时携带最后一轮非法输出（排障/转人工上下文，不作为交付物），CLI 同步输出。
- 研究脚本（evidence/）：`collect_golden_detail.py`、`anchor_probe.py`、`stability_probe.py`、`fmt_fidelity_bench.py`；新增原始数据 8 份。
- 测试 21 → 42 项（传输层退避 5 项 + 研究开关 9 项 + last_raw_config 断言等）。

### 关键结论
- glm-5.3-flash 同 v2 prompt 全量 golden 收敛 8/8（4-flash 稳定卡 05/08）——管线无缺陷，瓶颈在小模型反馈吸收能力。
- glm-4-flash 的两类失败（对抗性指令锚定、过约束松弛）对反馈模板升级/few-shot/重试加倍全部免疫；temperature≈0 输出仍非逐字节确定（基础设施级随机性）。
- glm-5.3-flash 首发另有 ~20–33% 系统性 ID 改写失败模式（`_1` 实例化后缀/语义 ID 发明），可被 1 轮反馈修复。

### 修复
- 移除误提交的 `nl2config/__pycache__`（.gitignore 已覆盖）；README 快速开始修正为真实 CLI 参数（`--scenario` 已随 v1.0.0 移除）。

## [v1.0.0] - 2026-10-13

修复问题报告（Issue #1）的全部 7 类失败模式，21/21 测试通过，golden 回归全绿。

### 新增
- **结构校验器** `schema.py`：字段名/类型/嵌套/必填/枚举校验，命名漂移别名检测（消灭失败模式 2/3/4 的结构层）。
- **三层业务校验器** `validators.py`：引用完整性（幻觉 ID）、双端兼容矩阵、广告位上限、套餐白名单、渠道追踪参数格式；错误信息结构化并携带合法可选值。
- **校验-修复循环** `generator.py`：结构化反馈回喂 + 3 次重试上限 + 显式降级转人工（降级为产品功能，附完整失败原因）。
- **patch 引擎** `patch_engine.py`：RFC 6902 风格 op 子集；路径白名单、`manual_locked` 锁（自身/祖先/后代/移动源全防）、根替换禁止、应用后结构复检、原子回滚——**架构性消灭**失败模式 6（全量重写覆盖人工修改）。
- **平台资产注册表** `registry.py`：组件/模板/套餐/广告位约束，带 SCHEMA_VERSION 版本号。
- **golden 回归评测集**：8 对需求→期望配置 + 指标（一次通过率 37.5%、收敛率 100%、幻觉 ID 率 12.5% 全捕获）。
- **CLI**：`generate` / `patch` / `regress` 三条子命令。
- 测试 21 项：7 类失败模式逐一对位 + 降级路径 + patch 安全 7 项 + golden 回归；CI（GitHub Actions，Python 3.11）。

### 修复
- naive 管线裸输出直通的问题：全部输出必须过四层校验，只存在 `ok`（全绿）与 `degraded`（附原因）两个状态。
- 编辑全量重写问题：模型只允许产 patch，且 patch 受白名单与锁双重约束。

## [v0.1.0] - 2026-10-13

缺陷基线（现状快照）：LLM 裸输出 JSON 直接当配置结果。

- naive 管线 `api.py`：无校验、无重试、无降级；patch 盲目应用（无白名单/无锁/允许整树替换）。
- 同一套测试在基线上 26 项失败——即问题报告的复现材料（见 docs/02）。
