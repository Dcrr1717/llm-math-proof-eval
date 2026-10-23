"""Generate SYNTHETIC sample results so the report renders without an API key.

Nothing here comes from a real model. The script picks, per model, which
problems are "missed" and with which plausible wrong answer, writes correct
answers in deliberately varied but equivalent notations (LaTeX, decimals,
"z = 4", ...) to exercise the grader, and draws token counts from a seeded RNG.
Every row is marked ``"synthetic": true`` and the report carries a banner.

Correctness is NOT stored here: ``run_eval.py --from-results`` re-grades each
row from its response text with the real SymPy grader.

    python scripts/make_sample_results.py      # rewrites sample_results.jsonl
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_eval import cost_usd, load_problems, write_jsonl  # noqa: E402

SEED = 20261023

# Equivalent-but-different notations for correct answers.
CORRECT_FORMS = {
    "ALG-03": "z = 4",
    "ALG-04": r"\frac{2575}{10302}",
    "COMB-01": "14,833",
    "CALC-01": "0.5",
    "CALC-02": r"-\frac{\pi \ln 2}{2}",
    "CALC-03": r"\frac{\pi^2 - 6}{6}",
    "CALC-04": r"\frac{22}{7} - \pi",
    "PRF-01": r"\frac{n \cdot 2^n}{2}",
    "PRF-02": r"\left(\frac{n(n+1)}{2}\right)^2",
    "PRF-03": r"1 - \frac{1}{n+1}",
}

# Synthetic misses per model: problem id -> wrong answer (None = truncated, no answer line).
MISSES = {
    "claude-opus-5-5": {"CALC-02": r"-\pi \ln 2"},
    "claude-sonnet-5-5": {"ALG-01": "10", "COMB-04": "165", "CALC-02": r"-\frac{\pi}{2}\ln 2 + 1"},
    "claude-haiku-5-5": {
        "ALG-01": "10",
        "ALG-02": "15",
        "NT-02": "3",
        "NT-03": None,
        "COMB-02": "924",
        "COMB-04": "165",
        "CALC-02": r"-\pi \ln 2",
        "CALC-04": r"\pi - \frac{22}{7}",
    },
}

# (output-token ranges by difficulty, tokens/second) - illustrative only.
PROFILE = {
    "claude-opus-5-5": ({"easy": (1200, 3500), "medium": (3000, 9000), "hard": (7000, 18000)}, 65),
    "claude-sonnet-5-5": ({"easy": (1000, 3000), "medium": (2500, 8000), "hard": (6000, 16000)}, 90),
    "claude-haiku-5-5": ({"easy": (700, 2000), "medium": (1500, 5000), "hard": (4000, 12000)}, 160),
}


def main() -> None:
    rng = random.Random(SEED)
    problems = load_problems(ROOT / "problems.jsonl")
    rows = []
    for model, (ranges, tps) in PROFILE.items():
        for p in problems:
            lo, hi = ranges[p["difficulty"]]
            out_tok = rng.randint(lo, hi)
            in_tok = 150 + len(p["statement"]) // 4 + rng.randint(0, 10)
            miss = MISSES[model]
            stop_reason = "end_turn"
            if p["id"] in miss and miss[p["id"]] is None:
                text = "[synthetic sample - not a real model output]\n... (reasoning cut off)"
                stop_reason = "max_tokens"
                out_tok = 64_000
            else:
                ans = miss.get(p["id"], CORRECT_FORMS.get(p["id"], p["answer"]))
                text = f"[synthetic sample - not a real model output]\n...\nFINAL ANSWER: {ans}"
            rows.append({
                "id": p["id"],
                "topic": p["topic"],
                "difficulty": p["difficulty"],
                "format": p["format"],
                "model": model,
                "effort": "high",
                "gold": p["answer"],
                "synthetic": True,
                "served_model": model,
                "stop_reason": stop_reason,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": round(cost_usd(model, in_tok, out_tok), 6),
                "latency_s": round(1.0 + out_tok / tps + rng.uniform(0, 2), 2),
                "response_text": text,
                "status": "truncated" if stop_reason == "max_tokens" else "ok",
            })
    write_jsonl(ROOT / "sample_results.jsonl", rows)
    print(f"wrote {len(rows)} synthetic rows to sample_results.jsonl")


if __name__ == "__main__":
    main()
