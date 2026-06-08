"""The eval loop: cases x models -> results."""

from __future__ import annotations
import json
import sys
from dataclasses import dataclass, asdict
from typing import Any

from models import Model
from scorers import SCORERS
from tools import TOOL_SCHEMAS


@dataclass
class CaseResult:
    case_id: str
    model: str
    score: float
    passed: bool
    latency_ms: int
    cost_usd: float
    output: str
    trace: dict

    def to_dict(self) -> dict:
        return asdict(self)


def load_cases(path: str) -> list[dict]:
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def run_suite(cases: list[dict], models: list[Model]) -> list[CaseResult]:
    results: list[CaseResult] = []
    total = len(cases) * len(models)
    print(f"Running {len(cases)} cases x {len(models)} models = {total} evals")
    for model in models:
        for case in cases:
            scorer = SCORERS[case["scorer"]]
            resp = model.complete(case["prompt"], TOOL_SCHEMAS)
            score = scorer(case, resp)
            results.append(CaseResult(
                case_id=case["id"],
                model=model.id,
                score=score,
                passed=score >= 1.0,
                latency_ms=resp.latency_ms,
                cost_usd=resp.cost_usd,
                output=resp.text if resp.text else json.dumps(resp.tool_calls),
                trace={**resp.trace, "tool_calls": resp.tool_calls},
            ))
            sys.stdout.write("." if score >= 1.0 else "F")
            sys.stdout.flush()
    print()
    return results
