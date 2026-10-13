"""命令行入口：
  python -m nl2config.cli generate --requirement "..." [--max-retries 3]
  python -m nl2config.cli patch --config cfg.json --patch patch.json [--locked /pages/0/components/1/props]
  python -m nl2config.cli regress

generate/regress 走真实 LLM（OpenAI 兼容协议），需环境变量
NL2CONFIG_API_KEY（或 OPENAI_API_KEY）；可选 NL2CONFIG_BASE_URL / NL2CONFIG_MODEL。
"""
import argparse
import json
import sys
from pathlib import Path

from .api import apply_patch, generate_config, run_golden_regression
from .llm import LlmConfigError

def main(argv=None):
    parser = argparse.ArgumentParser(prog="nl2config", description="自然语言→低代码配置 约束生成层")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="需求 → 合法配置（含校验-修复循环与降级）")
    g.add_argument("--requirement", required=True)
    g.add_argument("--max-retries", type=int, default=3)

    p = sub.add_parser("patch", help="应用受约束的增量 patch")
    p.add_argument("--config", required=True, help="配置 JSON 文件")
    p.add_argument("--patch", required=True, help="patch JSON 文件（op 数组）")
    p.add_argument("--locked", nargs="*", default=[], help="manual_locked 路径列表")

    r = sub.add_parser("regress", help="跑 golden 回归评测集")

    args = parser.parse_args(argv)
    if args.cmd == "generate":
        try:
            result = generate_config(args.requirement, max_retries=args.max_retries)
        except LlmConfigError as e:
            print(f"错误：{e}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps({
            "status": result.status, "attempts": result.attempts,
            "config": result.config, "violation_history": result.violation_history,
            "degraded_reasons": result.degraded_reasons,
        }, ensure_ascii=False, indent=2))
    elif args.cmd == "patch":
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        patch = json.loads(Path(args.patch).read_text(encoding="utf-8"))
        result = apply_patch(config, patch, manual_locked=args.locked)
        print(json.dumps({
            "ok": result.ok, "applied": result.applied,
            "rejections": [x.__dict__ for x in result.rejections],
            "config": result.config,
        }, ensure_ascii=False, indent=2))
        sys.exit(0 if result.ok else 1)
    elif args.cmd == "regress":
        try:
            report = run_golden_regression()
        except LlmConfigError as e:
            print(f"错误：{e}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
