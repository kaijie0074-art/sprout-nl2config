"""命令行入口：
  python -m nl2config.cli generate --requirement "..." --scenario hallucinated_id
  python -m nl2config.cli patch --config cfg.json --patch patch.json [--locked /pages/0/components/1/props]
  python -m nl2config.cli regress
"""
import argparse
import json
import sys
from pathlib import Path

from .api import apply_patch, generate_config, run_golden_regression


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nl2config", description="自然语言→低代码配置 约束生成层")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="需求 → 合法配置（含校验-修复循环与降级）")
    g.add_argument("--requirement", required=True)
    g.add_argument("--scenario", default="ok")
    g.add_argument("--max-retries", type=int, default=3)

    p = sub.add_parser("patch", help="应用受约束的增量 patch")
    p.add_argument("--config", required=True, help="配置 JSON 文件")
    p.add_argument("--patch", required=True, help="patch JSON 文件（op 数组）")
    p.add_argument("--locked", nargs="*", default=[], help="manual_locked 路径列表")

    r = sub.add_parser("regress", help="跑 golden 回归评测集")

    args = parser.parse_args(argv)
    if args.cmd == "generate":
        result = generate_config(args.requirement, scenario=args.scenario, max_retries=args.max_retries)
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
        report = run_golden_regression()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
