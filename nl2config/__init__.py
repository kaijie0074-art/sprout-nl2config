"""nl2config —— 自然语言 → 低代码平台私有配置的约束生成层。

对应岗位难题③：让 LLM 把中文口语需求**确定性**地翻译成 100% 合法的
低代码平台配置树。分层解法：
  1. 结构约束（schema 校验）
  2. 校验-修复循环（结构化反馈 + 有限重试 + 显式降级转人工）
  3. 合法枚举注入（注册表 + 错误信息携带可选值）
  4. 编辑走 patch（路径白名单 + manual_locked 锁，架构上杜绝全量重写）
  5. golden 回归评测集（一次通过率 / 收敛分布 / 幻觉 ID 率）
"""

__version__ = "1.0.0"

from .api import GenerationResult, PatchResult, apply_patch, generate_config, run_golden_regression  # noqa: F401
