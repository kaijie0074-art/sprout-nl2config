# sprout-nl2config

> **自然语言 → 低代码平台私有配置的约束生成层**（问题③）
>
> 让 LLM 把中文口语需求**确定性**地翻译成 100% 合法的低代码平台配置树——不存在"输出大概是对的"这个状态。

![CI](https://github.com/kaijie0074-art/sprout-nl2config/actions/workflows/ci.yml/badge.svg)

## 对应岗位难题

末龙科技 AI 应用工程师岗·三大技术难题之**问题③**：私有 DSL 约束生成。LLM 原生输出空间是自由文本，目标是带四层约束（结构/引用/语义/业务）的形式语言，两个空间性质根本不同——这不是"prompt 写得好不好"，是**受限形式语言生成**问题。

## 架构

```mermaid
flowchart LR
    A[中文口语需求] --> B[真实 LLM<br/>OpenAI 兼容协议]
    B --> C[结构校验<br/>schema.py]
    C -->|结构违规| F[结构化反馈回喂<br/>错误码+路径+可选值]
    C -->|通过| D[引用/语义/业务校验<br/>validators.py]
    D -->|违规| F
    D -->|全绿| E[✅ ok 返回配置]
    F --> B
    F -->|超过 3 次重试| G[🚸 degraded 显式降级转人工<br/>附完整失败原因]
    H[修改指令] --> I[patch 引擎<br/>RFC6902 子集]
    I --> J{路径白名单?<br/>manual_locked?<br/>根替换?}
    J -->|任一违规| K[❌ 拒绝·原子回滚]
    J -->|全过| L[✅ 增量应用]
```

五层解法（详见 [docs/04-修复设计与引用.md](docs/04-修复设计与引用.md)）：
1. **结构约束**——手写 schema 校验器钉住字段名/类型/嵌套/必填/枚举；
2. **校验-修复循环**——结构化错误反馈（含合法可选值）+ 3 次重试上限 + 显式降级转人工；
3. **合法枚举注入**——注册表 + 错误信息携带可选值，教会模型"下次怎么改"；
4. **编辑走 patch**——路径白名单 + `manual_locked` 锁 + 根替换禁止，**架构上**杜绝全量重写覆盖人工修改；
5. **golden 回归评测集**——8 对需求→期望配置，量化一次通过率/收敛率/幻觉 ID 率。

## 快速开始

```bash
# 需求 → 配置（真实 LLM；幻觉 ID 场景通常第 2 轮收敛）
export NL2CONFIG_API_KEY=...   # 可选 NL2CONFIG_BASE_URL / NL2CONFIG_MODEL / NL2CONFIG_TIMEOUT
python3 -m nl2config.cli generate --requirement "做个视频站"

# 不可纠正场景 → 显式降级转人工（附失败原因与最后一轮非法输出）
python3 -m nl2config.cli generate --requirement "顽固场景"

# 受约束增量修改（触锁即拒）
python3 -m nl2config.cli patch --config examples/site.json \
  --patch examples/patch.json --locked /pages/0/components/1/props

# golden 回归（含指标；无凭证时 live 用例自动跳过）
python3 -m nl2config.cli regress
```

## 验证

```bash
python3 -m unittest discover -s tests -v   # 42 项全绿（live 用例无凭证自动跳过）
```

修复前后的完整对比见 [docs/06-回归记录.md](docs/06-回归记录.md)：同一套测试在缺陷基线上 **26 项失败**，修复后全部通过；校验-修复循环保证"含重试收敛 + 永不返回非法配置"。golden 指标（一次通过率/收敛率/幻觉 ID 率）对真实 LLM 在线度量（`python -m nl2config.cli regress`，需凭证）。

深潜研究（2026-10-14）：repair 类不收敛的根因解剖与模型能力上限——glm-4-flash 的失败
（指令锚定/过约束松弛）对反馈模板升级、few-shot、重试加倍全部免疫，glm-5.3-flash 同反馈一轮修复；
temperature≈0 下输出仍非逐字节确定。完整问题链 Q1–Q8 与复现命令见
[docs/research/deep-dive-20261014.md](docs/research/deep-dive-20261014.md)。

## 目录结构

```
nl2config/
  schema.py        # 第一层：结构约束校验器
  validators.py    # 二~四层：引用/语义/业务校验（结构化错误+可选值）
  generator.py     # 校验-修复循环 + 显式降级
  patch_engine.py  # 第四层：增量 patch（白名单/锁/全量重写防护/原子性）
  golden.py        # 第五层：回归评测集与指标
  llm.py           # 真实 LLM 客户端（OpenAI 兼容协议，环境变量凭证）
  registry.py      # 平台资产注册表（组件/模板/套餐/广告位约束，带版本）
  api.py           # 稳定 API 表面（baseline 与最终态共用签名）
tests/             # 42 项回归测试（baseline 上 26 项失败 = 复现材料；live 用例凭证门控）
data/golden/       # 8 对 golden pairs
docs/              # 问题报告 / 复现 / 调研 / 设计 / 覆盖 / 回归
examples/          # CLI 演示样例
```

## 工程过程

本仓库按真实工程流程搭建：问题报告见 [Issue #1](https://github.com/kaijie0074-art/sprout-nl2config/issues/1)，修复走 [PR #2](https://github.com/kaijie0074-art/sprout-nl2config/pull/2)（含评审意见、采纳记录、负责人验收），发布记录见 [Releases](https://github.com/kaijie0074-art/sprout-nl2config/releases)。

## 声明

**说明**：针对末龙科技 AI 应用工程师岗三大技术难题之问题③的工程化实现（2026-10）。LLM 为真实 API（OpenAI 兼容协议，默认智谱，可切 DeepSeek 等）；低代码平台 schema 为示例资产；技术路线源自公开调研与业务链路推演。开源调研引用见 [docs/03](docs/03-开源调研.md)。
