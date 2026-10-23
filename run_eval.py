"""Benchmark Claude models on verifier-graded math problems.

Each problem in ``problems.jsonl`` is sent to the Messages API, the final
answer is graded by the SymPy verifier in ``grader.py``, and USD cost is
computed from the token usage the API reports. Results go to a JSONL file and
a markdown report.

Examples
--------
    # No API key needed: re-grade the bundled synthetic sample and render the report
    python run_eval.py --from-results sample_results.jsonl

    # Live run (costs money): first 5 problems on the default model
    export ANTHROPIC_API_KEY=...        # or put it in .env
    python run_eval.py --limit 5

    # Compare models at a given effort level
    python run_eval.py --models claude-opus-5-5,claude-sonnet-5-5 --effort high
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grader import grade

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
DEFAULT_MAX_TOKENS = 64_000

SYSTEM_PROMPT = """You are solving competition mathematics problems.
Work carefully and check your result. For problems that ask for a proof, \
write a concise, rigorous proof before giving the closed form.

Finish with exactly one line of the form
FINAL ANSWER: <answer>
where <answer> is an exact mathematical expression (integers, fractions, \
pi, sqrt, log, and the variable n are allowed). Do not give decimal \
approximations and do not put anything after that line."""


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    output: float
    # Optional long-prompt tier: prompts above `threshold` input tokens bill at these rates.
    long_threshold: int | None = None
    long_input: float | None = None
    long_output: float | None = None


# First-party Claude API list prices (USD / 1M tokens). Thinking tokens are
# billed as output tokens and are included in usage.output_tokens.
# Update this table if prices change; unknown models are reported with cost = None.
PRICING: dict[str, Price] = {
    "claude-fable-5-1": Price(10.00, 50.00),
    "claude-opus-5-5": Price(4.00, 20.00),
    "claude-opus-5": Price(5.00, 25.00),
    "claude-opus-4-8": Price(5.00, 25.00),
    "claude-sonnet-5-5": Price(2.00, 10.00),
    "claude-sonnet-5": Price(2.00, 10.00),
    "claude-haiku-5-5": Price(0.10, 0.50, long_threshold=100_000, long_input=0.50, long_output=2.50),
}

# Models that accept server-side refusal fallbacks (`fallbacks: "default"`).
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = PRICING.get(model)
    if price is None:
        return None
    in_rate, out_rate = price.input, price.output
    if price.long_threshold is not None and input_tokens > price.long_threshold:
        in_rate, out_rate = price.long_input, price.long_output
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def load_problems(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_results(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def grade_record(record: dict) -> dict:
    """(Re)grade a result record from its raw response text."""
    g = grade(record.get("response_text") or "", record["gold"])
    record.update(extracted=g.extracted, correct=g.correct, grade_method=g.method)
    return record


# --------------------------------------------------------------------------
# API calls
# --------------------------------------------------------------------------

async def solve_one(client, problem: dict, model: str, effort: str, max_tokens: int,
                    sem: asyncio.Semaphore) -> dict:
    import anthropic

    record = {
        "id": problem["id"],
        "topic": problem["topic"],
        "difficulty": problem["difficulty"],
        "format": problem["format"],
        "model": model,
        "effort": effort,
        "gold": problem["answer"],
        "synthetic": False,
    }
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=[{"role": "user", "content": problem["statement"]}],
    )
    if model in FALLBACK_MODELS:
        kwargs.update(betas=[FALLBACK_BETA], fallbacks="default")

    async with sem:
        start = time.perf_counter()
        try:
            async with client.beta.messages.stream(**kwargs) as stream:
                message = await stream.get_final_message()
        except anthropic.RateLimitError as e:
            return {**record, "status": "error", "error": f"rate_limited: {e.message}"}
        except anthropic.APIStatusError as e:
            return {**record, "status": "error", "error": f"http_{e.status_code}: {e.message}"}
        except anthropic.APIConnectionError as e:
            return {**record, "status": "error", "error": f"connection: {e}"}
        latency = time.perf_counter() - start

    served_model = message.model or model
    usage = message.usage
    text = "".join(b.text for b in message.content if b.type == "text")
    record.update(
        served_model=served_model,
        stop_reason=message.stop_reason,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=cost_usd(served_model, usage.input_tokens, usage.output_tokens),
        latency_s=round(latency, 2),
        response_text=text,
        status={"refusal": "refusal", "max_tokens": "truncated"}.get(message.stop_reason, "ok"),
    )
    return grade_record(record)


async def run_live(problems: list[dict], models: list[str], effort: str, max_tokens: int,
                   concurrency: int) -> list[dict]:
    from anthropic import AsyncAnthropic

    sem = asyncio.Semaphore(concurrency)
    async with AsyncAnthropic() as client:
        tasks = [solve_one(client, p, m, effort, max_tokens, sem) for m in models for p in problems]
        results = []
        for coro in asyncio.as_completed(tasks):
            r = await coro
            mark = "✓" if r.get("correct") else ("!" if r.get("status") == "error" else "✗")
            cost = r.get("cost_usd")
            print(f"  {mark} {r['model']:<20} {r['id']:<8} "
                  f"{'' if cost is None else f'${cost:.4f}'}  {r.get('extracted') or r.get('error', '')}")
            results.append(r)
    order = {p["id"]: i for i, p in enumerate(problems)}
    return sorted(results, key=lambda r: (models.index(r["model"]), order[r["id"]]))


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def _fmt_usd(x: float | None, digits: int = 4) -> str:
    return "n/a" if x is None else f"${x:,.{digits}f}"


def summarize(results: list[dict]) -> dict[str, dict]:
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)
    summary = {}
    for model, rows in by_model.items():
        n = len(rows)
        correct = sum(1 for r in rows if r.get("correct"))
        costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
        total_cost = sum(costs) if costs else None
        lat = [r["latency_s"] for r in rows if r.get("latency_s") is not None]
        out_tok = [r["output_tokens"] for r in rows if r.get("output_tokens") is not None]
        summary[model] = {
            "n": n,
            "correct": correct,
            "accuracy": correct / n if n else 0.0,
            "total_cost": total_cost,
            "cost_per_correct": (total_cost / correct) if (total_cost is not None and correct) else None,
            "mean_latency": sum(lat) / len(lat) if lat else None,
            "mean_output_tokens": sum(out_tok) / len(out_tok) if out_tok else None,
            "errors": sum(1 for r in rows if r.get("status") in {"error", "refusal", "truncated"}),
        }
    return summary


def _breakdown(results: list[dict], key: str, models: list[str]) -> list[str]:
    cells: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for r in results:
        cells[(r[key], r["model"])].append(bool(r.get("correct")))
    rank = {"easy": 0, "medium": 1, "hard": 2}
    values = sorted({r[key] for r in results}, key=lambda v: (rank.get(v, 9), v))
    lines = [f"| {key} | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for v in values:
        row = []
        for m in models:
            xs = cells.get((v, m), [])
            row.append(f"{sum(xs)}/{len(xs)}" if xs else "-")
        lines.append(f"| {v} | " + " | ".join(row) + " |")
    return lines


def render_report(results: list[dict], source: str) -> str:
    models = list(dict.fromkeys(r["model"] for r in results))
    summary = summarize(results)
    synthetic = any(r.get("synthetic") for r in results)
    effort = sorted({r.get("effort", "?") for r in results})
    lines = ["# Math eval report", ""]
    if synthetic:
        lines += [
            "> **SYNTHETIC DEMO DATA.** These rows were generated by "
            "`scripts/make_sample_results.py` to exercise the grading and cost pipeline "
            "without an API key. They are not real model outputs and say nothing about "
            "any model's actual accuracy. Run `python run_eval.py` with a key for real numbers.",
            "",
        ]
    lines += [
        f"- Source: `{source}`",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Problems per model: {max(s['n'] for s in summary.values())}; effort: {', '.join(effort)}",
        "- Grading: SymPy symbolic equivalence (`grader.py`); cost from API-reported token usage "
        "at list prices (`PRICING` in `run_eval.py`).",
        "",
        "## Summary",
        "",
        "| Model | Accuracy | Correct | Total cost | Cost / correct | Mean output tokens | Mean latency | Failed calls* |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in models:
        s = summary[m]
        lat = "n/a" if s["mean_latency"] is None else f"{s['mean_latency']:.1f}s"
        tok = "n/a" if s["mean_output_tokens"] is None else f"{s['mean_output_tokens']:,.0f}"
        lines.append(
            f"| `{m}` | {s['accuracy']:.0%} | {s['correct']}/{s['n']} | {_fmt_usd(s['total_cost'])} | "
            f"{_fmt_usd(s['cost_per_correct'])} | {tok} | {lat} | {s['errors']} |"
        )
    lines += ["", "\\* refusals, `max_tokens` truncations and API errors; these count as incorrect.",
              "", "## Accuracy by topic", ""] + _breakdown(results, "topic", models)
    lines += ["", "## Accuracy by difficulty", ""] + _breakdown(results, "difficulty", models)

    methods: dict[str, int] = defaultdict(int)
    for r in results:
        methods[r.get("grade_method", "?")] += 1
    lines += ["", "## How answers were graded", "", "| Method | Count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(methods.items())]

    misses = [r for r in results if not r.get("correct")]
    lines += ["", "## Incorrect or failed items", ""]
    if not misses:
        lines.append("None.")
    else:
        lines += ["| Model | Problem | Gold | Extracted | Method / status |", "|---|---|---|---|---|"]
        for r in misses:
            status = r.get("grade_method") or r.get("status")
            if r.get("status") not in (None, "ok"):
                status = f"{status} ({r['status']})"
            extracted = (r.get("extracted") or r.get("error") or "-").replace("|", "\\|")
            lines.append(f"| `{r['model']}` | {r['id']} | `{r['gold']}` | `{extracted}` | {status} |")
    lines.append("")
    return "\n".join(lines)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--problems", type=Path, default=ROOT / "problems.jsonl")
    p.add_argument("--models", default=os.environ.get("EVAL_MODEL", DEFAULT_MODEL),
                   help="comma-separated model IDs (default: $EVAL_MODEL or %(default)s)")
    p.add_argument("--effort", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--limit", type=int, default=None, help="only run the first N problems")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--out", type=Path, default=None, help="results JSONL (default: results/run-<timestamp>.jsonl)")
    p.add_argument("--report", type=Path, default=ROOT / "results" / "report.md")
    p.add_argument("--from-results", type=Path, default=None,
                   help="re-grade an existing results JSONL and render the report; no API calls")
    return p.parse_args(argv)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.from_results:
        results = [grade_record(r) for r in load_results(args.from_results)]
        if args.limit:
            keep = {p["id"] for p in load_problems(args.problems)[: args.limit]}
            results = [r for r in results if r["id"] in keep]
        report = render_report(results, str(args.from_results.name))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
        print(report)
        print(f"Report written to {args.report}")
        return 0

    _load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set, so no live API calls will be made.\n"
            "  - To run the benchmark: export ANTHROPIC_API_KEY=... (or copy .env.example to .env)\n"
            "  - To see the pipeline on bundled synthetic data:\n"
            "      python run_eval.py --from-results sample_results.jsonl"
        )
        return 0

    problems = load_problems(args.problems)
    if args.limit:
        problems = problems[: args.limit]
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in PRICING]
    if unknown:
        print(f"warning: no price entry for {unknown}; their cost will be reported as n/a", file=sys.stderr)

    print(f"Running {len(problems)} problems x {len(models)} model(s), effort={args.effort}")
    results = asyncio.run(run_live(problems, models, args.effort, args.max_tokens, args.concurrency))

    out = args.out or ROOT / "results" / f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.jsonl"
    write_jsonl(out, results)
    report = render_report(results, str(out.name))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print()
    print(report)
    print(f"Results: {out}\nReport:  {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
