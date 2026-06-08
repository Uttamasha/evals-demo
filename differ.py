"""Compares current results against a committed baseline.
Triggers regression on pass-rate drop, case flips, p95 latency jump, or cost jump."""

from __future__ import annotations
import statistics
from dataclasses import dataclass, field
from typing import Any

PASS_RATE_TOLERANCE = 0.02
LATENCY_TOLERANCE_PCT = 0.20
COST_TOLERANCE_PCT = 0.10

RED, GREEN, YELLOW, DIM, BOLD, RESET = (
    "\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[1m", "\033[0m",
)


@dataclass
class DiffReport:
    aggregate: dict
    per_case: list[dict]
    reasons: list[str] = field(default_factory=list)


def _key(r: dict) -> tuple[str, str]:
    return (r["case_id"], r["model"])


def _aggregate(results: list[dict]) -> dict:
    passed = sum(1 for r in results if r["passed"])
    scores = [r["score"] for r in results]
    latencies = sorted(r["latency_ms"] for r in results)
    p95_idx = max(0, int(len(latencies) * 0.95) - 1)
    return {
        "pass_rate": passed / len(results) if results else 0.0,
        "mean_score": statistics.mean(scores) if scores else 0.0,
        "p95_latency": latencies[p95_idx] if latencies else 0,
        "total_cost": round(sum(r["cost_usd"] for r in results), 6),
        "n": len(results),
    }


def diff(baseline: list[dict], current: list[dict]) -> DiffReport:
    b_agg, c_agg = _aggregate(baseline), _aggregate(current)
    aggregate = {
        "pass_rate_before": b_agg["pass_rate"], "pass_rate_after": c_agg["pass_rate"],
        "delta": c_agg["pass_rate"] - b_agg["pass_rate"],
        "mean_score_before": b_agg["mean_score"], "mean_score_after": c_agg["mean_score"],
        "p95_latency_before": b_agg["p95_latency"], "p95_latency_after": c_agg["p95_latency"],
        "total_cost_before": b_agg["total_cost"], "total_cost_after": c_agg["total_cost"],
    }

    b_map = {_key(r): r for r in baseline}
    per_case = []
    for r in current:
        k = _key(r)
        b = b_map.get(k)
        b_passed = b["passed"] if b else None
        c_passed = r["passed"]
        if b is None:
            flipped = "NEW"
        elif b_passed and not c_passed:
            flipped = "REGRESS"
        elif not b_passed and c_passed:
            flipped = "FIXED"
        else:
            flipped = "STABLE"
        per_case.append({
            "case_id": r["case_id"], "model": r["model"],
            "baseline_status": "PASS" if b_passed else ("FAIL" if b is not None else "—"),
            "current_status": "PASS" if c_passed else "FAIL",
            "flipped": flipped,
        })

    return DiffReport(aggregate=aggregate, per_case=per_case)


def is_regression(report: DiffReport) -> bool:
    a = report.aggregate
    reasons: list[str] = []
    if a["pass_rate_before"] - a["pass_rate_after"] > PASS_RATE_TOLERANCE:
        reasons.append(f"pass rate dropped {a['pass_rate_before']:.0%} → {a['pass_rate_after']:.0%}")
    flips = [c for c in report.per_case if c["flipped"] == "REGRESS"]
    if flips:
        ids = ", ".join(f"{c['case_id']}/{_short(c['model'])}" for c in flips)
        reasons.append(f"{len(flips)} case(s) flipped PASS→FAIL ({ids})")
    if a["p95_latency_before"] > 0:
        jump = (a["p95_latency_after"] - a["p95_latency_before"]) / a["p95_latency_before"]
        if jump > LATENCY_TOLERANCE_PCT:
            reasons.append(f"p95 latency +{jump:.0%}")
    if a["total_cost_before"] > 0:
        jump = (a["total_cost_after"] - a["total_cost_before"]) / a["total_cost_before"]
        if jump > COST_TOLERANCE_PCT:
            reasons.append(f"total cost +{jump:.0%}")
    report.reasons = reasons
    return bool(reasons)


def _short(model_id: str) -> str:
    if "haiku" in model_id: return "haiku"
    if "sonnet" in model_id: return "sonnet"
    return model_id


def _color_flip(s: str) -> str:
    return {"REGRESS": f"{RED}{s}{RESET}", "FIXED": f"{GREEN}{s}{RESET}",
            "NEW": f"{YELLOW}{s}{RESET}", "STABLE": f"{DIM}{s}{RESET}"}.get(s, s)


def print_diff_table(report: DiffReport) -> None:
    a = report.aggregate
    print(f"\n{BOLD}Aggregate{RESET}  baseline → current")
    print(f"  pass rate    {a['pass_rate_before']:.0%} → {a['pass_rate_after']:.0%} "
          f"(Δ {a['delta']:+.0%})")
    print(f"  p95 latency  {a['p95_latency_before']} ms → {a['p95_latency_after']} ms")
    print(f"  total cost   ${a['total_cost_before']:.4f} → ${a['total_cost_after']:.4f}")

    print(f"\n{BOLD}Per-case{RESET}")
    print(f"  {'case_id':<16} {'model':<8} {'before':<6} {'after':<6} status")
    for c in report.per_case:
        print(f"  {c['case_id']:<16} {_short(c['model']):<8} "
              f"{c['baseline_status']:<6} {c['current_status']:<6} {_color_flip(c['flipped'])}")
