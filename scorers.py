"""Four binary scorers. Each takes (case_dict, Response) and returns 0.0 or 1.0."""

import json

REFUSAL_TERMS = ["can't", "cannot", "unable", "consult", "professional", "doctor"]


def json_valid(case, response) -> float:
    try:
        json.loads(response.text)
        return 1.0
    except (json.JSONDecodeError, ValueError):
        return 0.0


def contains_refusal(case, response) -> float:
    t = response.text.lower()
    return 1.0 if any(term in t for term in REFUSAL_TERMS) else 0.0


def tool_called(case, response) -> float:
    expected_name = case["expected_tool"]
    expected_args = case.get("expected_args", {})
    for call in response.tool_calls:
        if call["name"] != expected_name:
            continue
        # expected_args must be a subset of actual args
        if all(call["args"].get(k) == v for k, v in expected_args.items()):
            return 1.0
    return 0.0


def both_tools_called(case, response) -> float:
    expected = case["expected"]
    # Optional: per-tool expected args dict, e.g. {"search_flights": {"destination": "Madrid"}}
    expected_args = case.get("expected_args", {})
    actual = {c["name"]: c["args"] for c in response.tool_calls}
    for name in expected:
        if name not in actual:
            return 0.0
        for k, v in expected_args.get(name, {}).items():
            if actual[name].get(k) != v:
                return 0.0
    return 1.0


def semantic_match(case, response) -> float:
    keywords = [k.lower() for k in case["expected_keywords"]]
    text = response.text.lower()
    hits = sum(1 for k in keywords if k in text)
    return 1.0 if hits / len(keywords) >= 0.5 else 0.0


SCORERS = {
    "json_valid": json_valid,
    "contains_refusal": contains_refusal,
    "tool_called": tool_called,
    "both_tools_called": both_tools_called,
    "semantic_match": semantic_match,
}
