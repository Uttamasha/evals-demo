"""CLI entrypoint: `python -m cli run` and `python -m cli baseline`."""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from runner import run_suite, load_cases
from models import Model
from differ import diff, is_regression, print_diff_table, BOLD, RESET, DIM, RED, GREEN

BASELINE_PATH = Path("baselines/main.json")
RESULTS_PATH = Path("results/latest.json")
GOLDEN_PATH = "golden_set.jsonl"

MODEL_IDS = {
    "sonnet": "gpt-4o",       # keep CLI keys "sonnet"/"haiku" for muscle memory;
    "haiku":  "gpt-4o-mini",  # they map to GitHub Models IDs under the hood.
}


def _short(mid: str) -> str:
    if "mini" in mid:
        return "mini"
    if mid == "gpt-4o":
        return "gpt-4o"
    if "haiku" in mid:
        return "haiku"
    if "sonnet" in mid:
        return "sonnet"
    return mid


def _print_per_model_summary(results: list[dict]) -> None:
    by_model: dict[str, list[dict]] = {}
    for r in results:
        by_model.setdefault(r["model"], []).append(r)
    print(f"\n{BOLD}Per-model summary{RESET}")
    print(f"  {'model':<8} {'pass':<8} {'mean':<6} {'p95 ms':<8} {'cost':<8}")
    for mid, rs in by_model.items():
        passed = sum(1 for r in rs if r["passed"])
        mean_score = sum(r["score"] for r in rs) / len(rs)
        lats = sorted(r["latency_ms"] for r in rs)
        p95 = lats[max(0, int(len(lats) * 0.95) - 1)]
        cost = sum(r["cost_usd"] for r in rs)
        print(f"  {_short(mid):<8} {passed}/{len(rs):<6} {mean_score:<6.2f} "
              f"{p95:<8} ${cost:<.4f}")


def _build_models(keys: list[str], mock: bool) -> list[Model]:
    return [Model(MODEL_IDS[k], mock=mock) for k in keys]


def cmd_run(args) -> int:
    cases = load_cases(GOLDEN_PATH)
    model_keys = args.models if args.models else ["sonnet", "haiku"]
    models = _build_models(model_keys, mock=args.mock)
    results = run_suite(cases, models)
    results_dicts = [r.to_dict() for r in results]

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results_dicts, indent=2))

    # 1. Per-model summary
    _print_per_model_summary(results_dicts)

    if args.no_baseline or not BASELINE_PATH.exists():
        if not args.no_baseline:
            print(f"\n{DIM}(no baseline at {BASELINE_PATH} — skipping diff){RESET}")
        return 0

    # 2. Per-case diff
    baseline = json.loads(BASELINE_PATH.read_text())
    report = diff(baseline, results_dicts)
    print_diff_table(report)

    # 3. Verdict
    if is_regression(report):
        print(f"\n{RED}{BOLD}❌ REGRESSION DETECTED:{RESET} " + "; ".join(report.reasons))
        return 1
    print(f"\n{GREEN}{BOLD}✅ NO REGRESSION{RESET}")
    return 0


def cmd_baseline(args) -> int:
    if BASELINE_PATH.exists() and not args.yes:
        ans = input(f"Overwrite {BASELINE_PATH}? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted.")
            return 1
    cases = load_cases(GOLDEN_PATH)
    models = _build_models(["sonnet", "haiku"], mock=args.mock)
    results = run_suite(cases, models)
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps([r.to_dict() for r in results], indent=2))
    print(f"\nBaseline saved to {BASELINE_PATH}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="cli", description="Tiny eval harness.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="Run evals and compare to baseline.")
    pr.add_argument("--models", nargs="+", choices=["sonnet", "haiku"], default=None)
    pr.add_argument("--no-baseline", action="store_true")
    pr.add_argument("--mock", action="store_true", help="Skip Anthropic API; use canned responses.")
    pr.set_defaults(func=cmd_run)

    pb = sub.add_parser("baseline", help="Overwrite baselines/main.json.")
    pb.add_argument("--yes", "-y", action="store_true", help="Skip confirm prompt.")
    pb.add_argument("--mock", action="store_true")
    pb.set_defaults(func=cmd_baseline)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
