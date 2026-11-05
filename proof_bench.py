"""Proof benchmark: Claude models write proofs of lemmas from recent peer-reviewed
papers, and a blind judge grades each proof against the paper's key steps.

The items, the proofs and the judgments are private (``private/``, gitignored), so
the set cannot leak into training data. Only aggregate scores are published, in
``results/proof_bench_report.md``.

Item schema (one JSON object per line in ``private/items.jsonl``)::

    {"id": "tda-01", "area": "topology",
     "source": {"citation": "...", "doi": "...", "arxiv": "2508.01234",
                "arxiv_v1": "2025-08-03", "label": "Lemma 4.3"},
     "definitions": "LaTeX", "statement": "LaTeX",
     "checkpoints": ["what a correct proof must establish", ...],
     "pitfalls": "where a naive proof goes wrong"}

Examples
--------
    python proof_bench.py solve --models claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5
    python proof_bench.py judge --judge claude-opus-5-5 --repeats 2
    python proof_bench.py judge --judge claude-sonnet-5-5 --repeats 1   # second judge
    python proof_bench.py report
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

from run_eval import FALLBACK_BETA, FALLBACK_MODELS, _load_dotenv, cost_usd

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private"
ITEMS = PRIVATE / "items.jsonl"
SOLUTIONS = PRIVATE / "solutions.jsonl"
JUDGMENTS = PRIVATE / "judgments.jsonl"
REPORT = ROOT / "results" / "proof_bench_report.md"

SOLVER_PROMPT = """You are a research mathematician. Prove the statement below.

Write a complete, rigorous proof at the level of a research paper. You may use \
standard results from graduate textbooks and the well-known literature if you state \
them precisely, but you may not assume the statement itself or any equivalent \
reformulation of it. If you believe the statement is false as written, say so and \
give a counterexample instead."""

JUDGE_PROMPT = """You are grading a proof written by a candidate for a research-level \
mathematical statement. You are given the statement, the definitions it uses, and \
the key steps of the proof published in a peer-reviewed paper, together with known \
pitfalls.

Grade the CANDIDATE proof for correctness and completeness:
- A different route from the published one is fine if it is rigorous. The key steps \
are a guide to what must be established somewhere, not a required outline.
- Check every nontrivial claim. Unjustified "clearly", hand-waving at the crucial \
step, circular use of the statement, a cited result that does not exist or does not \
apply, or a computation that is wrong are all gaps.
- Do not reward length or confident tone. Do not give credit for steps that are \
announced but not carried out.

Verdict scale:
- "correct": complete and rigorous; at most cosmetic slips.
- "minor_gaps": the argument is right, but one or two steps a specialist could fill \
in routinely are missing or sloppy.
- "major_gap": a crucial step is missing, unjustified or wrong, although the overall \
idea may be viable.
- "wrong": the approach does not work, the proof proves something else, or it \
claims the statement is false when it is true.

Reply with your analysis, then end with exactly one JSON object in a ```json fenced \
block, with these keys:
{"checkpoints": [{"step": 1, "status": "established|partial|missing", "note": "..."}],
 "fatal_issue": "the main error, or null",
 "verdict": "correct|minor_gaps|major_gap|wrong",
 "score": 0-10}"""

SCORE_OF = {"correct": 1.0, "minor_gaps": 0.75, "major_gap": 0.25, "wrong": 0.0}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def problem_text(item: dict) -> str:
    parts = []
    if item.get("definitions"):
        parts.append("Definitions and notation:\n" + item["definitions"].strip())
    parts.append("Statement to prove:\n" + item["statement"].strip())
    return "\n\n".join(parts)


async def call(client, model: str, system: str, user: str, effort: str,
               max_tokens: int, sem: asyncio.Semaphore) -> dict:
    import anthropic

    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=[{"role": "user", "content": user}],
    )
    if model in FALLBACK_MODELS:
        kwargs.update(betas=[FALLBACK_BETA], fallbacks="default")
    async with sem:
        start = time.perf_counter()
        try:
            async with client.beta.messages.stream(**kwargs) as stream:
                message = await stream.get_final_message()
        except anthropic.APIError as e:
            return {"status": "error", "error": f"{type(e).__name__}: {e}"}
        latency = time.perf_counter() - start
    served = message.model or model
    u = message.usage
    return {
        "status": {"refusal": "refusal", "max_tokens": "truncated"}.get(
            message.stop_reason, "ok"),
        "served_model": served,
        "text": "".join(b.text for b in message.content if b.type == "text"),
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cost_usd": cost_usd(served, u.input_tokens, u.output_tokens),
        "latency_s": round(latency, 2),
    }


# --------------------------------------------------------------------------
# solve / judge
# --------------------------------------------------------------------------

async def solve(models: list[str], samples: int, effort: str, max_tokens: int,
                concurrency: int, max_cost: float) -> None:
    from anthropic import AsyncAnthropic

    items = load_jsonl(ITEMS)
    # truncations and refusals are final outcomes; only API errors are retried
    done = {(s["id"], s["model"], s["sample"]) for s in load_jsonl(SOLUTIONS)
            if s["status"] != "error"}
    todo = [(it, m, k) for it in items for m in models for k in range(samples)
            if (it["id"], m, k) not in done]
    print(f"[solve] items={len(items)} models={models} samples={samples} calls={len(todo)}")
    sem = asyncio.Semaphore(concurrency)
    spent = 0.0
    async with AsyncAnthropic() as client:
        async def one(it, m, k):
            r = await call(client, m, SOLVER_PROMPT, problem_text(it), effort, max_tokens, sem)
            return {"id": it["id"], "model": m, "sample": k, "effort": effort, **r}

        for fut in asyncio.as_completed([one(*t) for t in todo]):
            row = await fut
            append_jsonl(SOLUTIONS, row)
            spent += row.get("cost_usd") or 0.0
            print(f"  {row['id']:<10} {row['model']:<20} s{row['sample']} {row['status']:<9} "
                  f"out={row.get('output_tokens', 0):>6} spent=${spent:.2f}")
            if spent > max_cost:
                print(f"[stop] spent ${spent:.2f} > cap ${max_cost:.2f}")
                return


def judge_text(item: dict, proof: str) -> str:
    steps = "\n".join(f"{i}. {c}" for i, c in enumerate(item["checkpoints"], 1))
    return (f"{problem_text(item)}\n\n"
            f"Key steps of the published proof:\n{steps}\n\n"
            f"Known pitfalls:\n{item.get('pitfalls') or 'none recorded'}\n\n"
            f"CANDIDATE PROOF (author withheld):\n<<<\n{proof}\n>>>")


def parse_judgment(text: str) -> dict | None:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    for b in reversed(blocks):
        try:
            j = json.loads(b)
        except json.JSONDecodeError:
            continue
        if j.get("verdict") in SCORE_OF:
            return j
    return None


async def judge(judge_model: str, repeats: int, effort: str, max_tokens: int,
                concurrency: int, max_cost: float, ids: set[str] | None = None) -> None:
    from anthropic import AsyncAnthropic

    items = {it["id"]: it for it in load_jsonl(ITEMS)}
    sols = [s for s in load_jsonl(SOLUTIONS) if s["status"] == "ok"
            and (ids is None or s["id"] in ids)]
    done = {(j["id"], j["model"], j["sample"], j["judge"], j["repeat"])
            for j in load_jsonl(JUDGMENTS) if j.get("verdict")}
    todo = [(s, r) for s in sols for r in range(repeats)
            if (s["id"], s["model"], s["sample"], judge_model, r) not in done]
    print(f"[judge] judge={judge_model} proofs={len(sols)} repeats={repeats} calls={len(todo)}")
    sem = asyncio.Semaphore(concurrency)
    spent = 0.0
    async with AsyncAnthropic() as client:
        async def one(s, r):
            res = await call(client, judge_model, JUDGE_PROMPT,
                             judge_text(items[s["id"]], s["text"]), effort, max_tokens, sem)
            j = parse_judgment(res.get("text", "")) if res["status"] == "ok" else None
            return {"id": s["id"], "model": s["model"], "sample": s["sample"],
                    "judge": judge_model, "repeat": r,
                    "verdict": j and j["verdict"], "score": j and j.get("score"),
                    "judgment": j, "judge_text": res.get("text"),
                    "cost_usd": res.get("cost_usd"), "status": res["status"]}

        for fut in asyncio.as_completed([one(*t) for t in todo]):
            row = await fut
            append_jsonl(JUDGMENTS, row)
            spent += row.get("cost_usd") or 0.0
            print(f"  {row['id']:<10} {row['model']:<20} s{row['sample']} r{row['repeat']} "
                  f"{row['verdict'] or 'UNPARSED':<11} spent=${spent:.2f}")
            if spent > max_cost:
                print(f"[stop] spent ${spent:.2f} > cap ${max_cost:.2f}")
                return


# --------------------------------------------------------------------------
# report (aggregates only: no statements, proofs or judge text)
# --------------------------------------------------------------------------

def report() -> str:
    items = {it["id"]: it for it in load_jsonl(ITEMS)}
    sols = {(s["id"], s["model"], s["sample"]): s
            for s in load_jsonl(SOLUTIONS) if s["status"] != "error"}
    all_js = [j for j in load_jsonl(JUDGMENTS) if j.get("verdict")]

    # the primary judge is the one with the most judgments; any other judge is
    # reported separately, as an agreement check, and does not enter the scores
    by_judge: dict[str, list[dict]] = defaultdict(list)
    for j in all_js:
        by_judge[j["judge"]].append(j)
    primary = max(by_judge, key=lambda g: len(by_judge[g])) if by_judge else None
    js = by_judge.get(primary, [])

    # one score per proof: the mean over judge repeats; a truncated or refused
    # answer is not a proof and scores 0
    per_proof: dict[tuple, list[float]] = defaultdict(list)
    verdicts: dict[tuple, list[str]] = defaultdict(list)
    for k, s in sols.items():
        if s["status"] != "ok":
            per_proof[k].append(0.0)
            verdicts[k].append("no_proof")
    for j in js:
        k = (j["id"], j["model"], j["sample"])
        per_proof[k].append(SCORE_OF[j["verdict"]])
        verdicts[k].append(j["verdict"])

    models = sorted({k[1] for k in per_proof})
    lines = ["# Proof benchmark (private items)", "",
             f"{len(items)} items from peer-reviewed papers; proofs graded blind against the "
             "published key steps. Score per proof: correct 1, minor gaps 0.75, major gap "
             "0.25, wrong 0, averaged over judge repeats.", "",
             "| Model | Proofs | Mean score | Fully correct | Unfinished | Solve cost | "
             "Cost per proof |",
             "|---|---|---|---|---|---|---|"]
    for m in models:
        ks = [k for k in per_proof if k[1] == m]
        mean = sum(sum(per_proof[k]) / len(per_proof[k]) for k in ks) / len(ks)
        full = sum(all(v == "correct" for v in verdicts[k]) for k in ks)
        unfinished = sum(verdicts[k] == ["no_proof"] for k in ks)
        cost = sum(sols[k].get("cost_usd") or 0 for k in ks if k in sols)
        lines.append(f"| {m} | {len(ks)} | {mean:.2f} | {full}/{len(ks)} | {unfinished} | "
                     f"${cost:.2f} | ${cost / len(ks):.3f} |")

    # judge self-consistency: proofs whose repeats disagree on the verdict
    multi = [v for v in verdicts.values() if len(v) > 1]
    if multi:
        agree = sum(len(set(v)) == 1 for v in multi)
        lines += ["", f"Judge consistency: identical verdict on {agree}/{len(multi)} proofs "
                      "judged more than once."]

    # contamination split by arXiv v1 date
    lines += ["", "| Model | Mean score, arXiv v1 before 2026-01-01 | on or after |",
              "|---|---|---|"]
    for m in models:
        cells = []
        for early in (True, False):
            ks = [k for k in per_proof if k[1] == m and k[0] in items
                  and (items[k[0]]["source"].get("arxiv_v1", "") < "2026-01-01") == early]
            cells.append(f"{sum(sum(per_proof[k]) / len(per_proof[k]) for k in ks) / len(ks):.2f}"
                         f" (n={len(ks)})" if ks else "-")
        lines.append(f"| {m} | {cells[0]} | {cells[1]} |")

    # second judge(s): verdict agreement with the primary judge, proof by proof.
    # A proof "agrees" when the second judge's verdict equals every verdict of
    # the primary judge on it. The per-proof comparison (ids and verdicts only,
    # no text) is written next to the report.
    for other in sorted(g for g in by_judge if g != primary):
        other_v: dict[tuple, list[str]] = defaultdict(list)
        other_cost = 0.0
        for j in by_judge[other]:
            other_v[(j["id"], j["model"], j["sample"])].append(j["verdict"])
            other_cost += j.get("cost_usd") or 0.0
        shared = sorted(k for k in other_v if k in verdicts and verdicts[k] != ["no_proof"])
        rows = []
        for k in shared:
            a, b = sorted(set(verdicts[k])), sorted(set(other_v[k]))
            rows.append({"id": k[0], "model": k[1], "sample": k[2],
                         "primary_judge": primary, "primary_verdicts": verdicts[k],
                         "second_judge": other, "second_verdicts": other_v[k],
                         "agree": a == b})
        agree = sum(r["agree"] for r in rows)
        lines += ["", f"## Second judge ({other})", "",
                  f"Independent judge over the same proofs, {len(by_judge[other])} calls, "
                  f"${other_cost:.2f}. Same verdict as the primary judge ({primary}) on "
                  f"{agree}/{len(rows)} proofs "
                  f"({100 * agree / len(rows):.0f}%)." if rows else
                  f"Independent judge over the same proofs; no proof judged by both."]
        if rows:
            lines += ["", "| Model | Mean score ({primary}) | Mean score ({other}) |"
                      .format(primary=primary, other=other), "|---|---|---|"]
            for m in models:
                rs = [r for r in rows if r["model"] == m]
                if rs:
                    mp = sum(sum(SCORE_OF[v] for v in r["primary_verdicts"])
                             / len(r["primary_verdicts"]) for r in rs) / len(rs)
                    mo = sum(sum(SCORE_OF[v] for v in r["second_verdicts"])
                             / len(r["second_verdicts"]) for r in rs) / len(rs)
                    lines.append(f"| {m} | {mp:.2f} (n={len(rs)}) | {mo:.2f} (n={len(rs)}) |")
        disagreements = [r for r in rows if not r["agree"]]
        if disagreements:
            lines += ["", "Disagreements:", "",
                      f"| Item | Model | {primary} | {other} |", "|---|---|---|---|"]
            for r in disagreements:
                lines.append(f"| {r['id']} | {r['model']} | "
                             f"{', '.join(r['primary_verdicts'])} | "
                             f"{', '.join(r['second_verdicts'])} |")
        elif rows:
            lines += ["", "No disagreements."]
            if all(set(r["primary_verdicts"]) | set(r["second_verdicts"]) == {"correct"}
                   for r in rows):
                lines[-1] += (" Every finished proof got `correct` from both judges, so "
                              "this agreement says nothing about how strict the judges "
                              "are; the score differences between models come only from "
                              "unfinished (truncated) answers.")
        out = REPORT.with_name(REPORT.stem + "_second_judge.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        lines += ["", f"Per-proof verdicts of both judges: `{out.name}`."]

    text = "\n".join(lines) + "\n"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("solve")
    s.add_argument("--models", default="claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5")
    s.add_argument("--samples", type=int, default=1)
    j = sub.add_parser("judge")
    j.add_argument("--judge", default="claude-opus-5-5")
    j.add_argument("--repeats", type=int, default=2)
    j.add_argument("--ids", default=None, help="comma list of item ids (default: all)")
    for q in (s, j):
        q.add_argument("--effort", default="high")
        q.add_argument("--max-tokens", type=int, default=64_000)
        q.add_argument("--concurrency", type=int, default=6)
        q.add_argument("--max-cost", type=float, default=10.0, help="hard USD cap")
    sub.add_parser("report")
    a = p.parse_args(argv)

    if a.cmd == "report":
        print(report())
        return 0
    _load_dotenv()
    if a.cmd == "solve":
        asyncio.run(solve(a.models.split(","), a.samples, a.effort, a.max_tokens,
                          a.concurrency, a.max_cost))
    else:
        asyncio.run(judge(a.judge, a.repeats, a.effort, a.max_tokens,
                          a.concurrency, a.max_cost,
                          set(a.ids.split(",")) if a.ids else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
