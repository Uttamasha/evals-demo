"""Thin wrapper around GitHub Models (OpenAI-compatible API).

Also supports a deterministic --mock mode used for scaffolding and for the
conference demo's dry-run.
"""

from __future__ import annotations
import os
import time
import json as _json
from dataclasses import dataclass, field
from typing import Any

# GitHub Models endpoint (OpenAI-compatible).
GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"

# Per-model pricing in USD per 1k tokens (input, output).
# These are illustrative public OpenAI prices — used only for the cost column
# in the per-model summary table. GitHub Models itself is free at this tier.
PRICING = {
    "gpt-4o":      (0.0025,  0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
}


@dataclass
class Response:
    text: str
    tool_calls: list[dict]           # [{"name": str, "args": dict}, ...]
    latency_ms: int
    cost_usd: float
    trace: dict = field(default_factory=dict)


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert our Anthropic-style schemas to OpenAI function-tool format."""
    return [
        {
            "type": "function",
            "function": {
                "name":        t["name"],
                "description": t.get("description", ""),
                "parameters":  t["input_schema"],
            },
        }
        for t in tools
    ]


class Model:
    def __init__(self, id: str, mock: bool = False):
        self.id = id
        self.mock = mock
        if not mock:
            from openai import OpenAI  # lazy import so --mock works w/o key
            token = os.environ.get("GITHUB_MODELS_TOKEN", "").strip()
            if not token:
                raise RuntimeError(
                    "GITHUB_MODELS_TOKEN not set. Add it to .env or export it."
                )
            self._client = OpenAI(
                base_url=GITHUB_MODELS_BASE_URL,
                api_key=token,
            )

    def complete(self, prompt: str, tools: list[dict]) -> Response:
        if self.mock:
            return _mock_complete(self.id, prompt, tools)

        t0 = time.time()
        raw = self._client.chat.completions.create(
            model=self.id,
            messages=[{"role": "user", "content": prompt}],
            tools=_to_openai_tools(tools),
            temperature=0,  # determinism for the demo — point at this line on stage
            max_tokens=512,
        )
        latency_ms = int((time.time() - t0) * 1000)

        choice = raw.choices[0]
        text = choice.message.content or ""
        tool_calls: list[dict] = []
        for tc in (choice.message.tool_calls or []):
            try:
                args = _json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            tool_calls.append({"name": tc.function.name, "args": args})

        in_p, out_p = PRICING.get(self.id, (0.0, 0.0))
        usage = raw.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        cost = round((in_tok / 1000) * in_p + (out_tok / 1000) * out_p, 6)

        return Response(
            text=text,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
            cost_usd=cost,
            trace={
                "prompt": prompt,
                "model": self.id,
                "finish_reason": choice.finish_reason,
                "usage": {"in": in_tok, "out": out_tok},
            },
        )


# --- mock implementation -----------------------------------------------------

def _required_keys(tool_schema: dict) -> list[str]:
    return tool_schema["input_schema"].get("required", [])

def _find_tool(tools: list[dict], name: str) -> dict | None:
    for t in tools:
        if t["name"] == name:
            return t
    return None

def _mock_complete(model_id: str, prompt: str, tools: list[dict]) -> Response:
    """Deterministic canned responses. Reads the *schema* for tool arg keys so
    that renaming a parameter in tools.py actually changes the tool-call args
    (this is what makes the regression demo work in --mock mode)."""
    p = prompt.lower()
    text, tool_calls = "", []

    def call_flights(dest: str):
        schema = _find_tool(tools, "search_flights")
        if not schema:
            return
        key = _required_keys(schema)[0]  # respect whatever the schema says
        tool_calls.append({"name": "search_flights", "args": {key: dest}})

    def call_hotels(city: str):
        schema = _find_tool(tools, "search_hotels")
        if not schema:
            return
        key = _required_keys(schema)[0]
        tool_calls.append({"name": "search_hotels", "args": {key: city, "nights": 3}})

    if "ibuprofen" in p or "chest pain" in p or "diagnose" in p:
        text = "I can't give medical advice — please consult a doctor or other professional."
    elif "fruits" in p and "json" in p:
        text = '["apple", "banana", "cherry"]'
    elif "name" in p and "age" in p and "json" in p:
        text = '{"name": "Alice", "age": 30}'
    elif "flight and a hotel" in p or ("flight" in p and "hotel" in p):
        city = "Madrid" if "madrid" in p else "Paris"
        call_flights(city); call_hotels(city)
        text = f"Booking flight and hotel for {city}."
    elif "flight" in p or "flights" in p:
        dest = "Tokyo" if "tokyo" in p else "Paris" if "paris" in p else "Madrid"
        call_flights(dest)
        text = f"Searching flights to {dest}."
    elif "hotel" in p:
        city = "Berlin" if "berlin" in p else "Paris"
        call_hotels(city)
        text = f"Searching hotels in {city}."
    elif "rayleigh" in p or "sky is blue" in p:
        text = "The sky appears blue because shorter-wavelength blue light is scattered more by the atmosphere."
    elif "tcp" in p and "udp" in p:
        text = "TCP is a reliable, connection-oriented protocol with retransmission, while UDP is connectionless and unordered."
    else:
        text = "OK."

    # Fake but plausible numbers. mini is cheaper + faster.
    in_tok, out_tok = max(8, len(prompt) // 4), max(8, len(text) // 4)
    in_p, out_p = PRICING.get(model_id, (0.0, 0.0))
    cost = round((in_tok / 1000) * in_p + (out_tok / 1000) * out_p, 6)
    latency = 180 if "mini" in model_id else 420

    return Response(
        text=text, tool_calls=tool_calls,
        latency_ms=latency, cost_usd=cost,
        trace={"prompt": prompt, "model": model_id, "mock": True,
               "usage": {"in": in_tok, "out": out_tok}},
    )
