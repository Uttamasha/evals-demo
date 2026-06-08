# Running Evals & Catching Regressions — Demo Harness

A tiny, framework-free Python eval harness for the conference talk. 10 golden cases, 2 Claude models, 4 scorers, ~600 lines total. CI exits non-zero on regression.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env       # then paste your ANTHROPIC_API_KEY
```

Use `--mock` on any command to run with canned responses (no API key, no network).

## Commands

```bash
python -m cli run                 # both models, diff vs baseline, exit 1 on regression
python -m cli run --models sonnet # single model
python -m cli run --no-baseline   # skip the diff
python -m cli baseline            # overwrite baselines/main.json (with confirm)
```

## Demo walkthrough — the 6 beats

1. `cat golden_set.jsonl` — show the 10 cases, point at scorer types.
2. `python -m cli run` — green board, ✅ NO REGRESSION.
3. `git checkout demo/broken-tool` — one-line diff in `tools.py` (`destination` → `dest`).
4. `python -m cli run` — `tool_01`, `tool_02`, `tool_chain_01` flip to FAIL; ❌ REGRESSION DETECTED; exit code 1.
5. `cat results/latest.json | jq '.[] | select(.case_id == "tool_01")'` — show the trace and the bad args.
6. "If this were a PR, CI would block it here."

## Files

`tools.py` system under test · `models.py` Anthropic wrapper · `scorers.py` 4 scorers · `runner.py` loop · `differ.py` diff + thresholds · `cli.py` entrypoint.
