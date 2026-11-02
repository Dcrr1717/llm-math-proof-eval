# llm-math-proof-eval

A small, verifier-backed benchmark of Claude models on competition-style math
and short proof problems:

- **20 problems** in algebra, number theory, combinatorics and calculus, plus closed-form proof items. Every gold answer is re-derived by brute force or CAS in the test suite.
- **A SymPy grader** that checks symbolic equivalence: `\frac{n \cdot 2^n}{2}` matches `n*2**(n-1)`, and `0.5` matches `1/2`, but a decimal like `-1.0888` does not match `-π ln 2 / 2`.
- **An async runner** that calls the Claude Messages API, grades each answer, prices every call from its token usage, and writes a markdown report.
- **Lean 4 proofs** (over Mathlib) of three gold answers, so those labels are theorems and not just entries in an answer key.

It runs out of the box **with no API key**, using bundled synthetic sample data.

## Why verifier-backed math eval matters for model selection

Choosing a model for math-heavy work is a cost/accuracy trade-off, and you
need trustworthy numbers on both sides:

1. **String matching under-counts correct answers.** `22/7 - pi`, `\frac{22-7\pi}{7}` and `(22 - 7 pi)/7` are the same number. Exact-match grading marks two of them wrong and penalizes models for notation instead of mathematics. A symbolic grader removes that noise, so accuracy differences between models are real differences.
2. **LLM-as-judge graders drift and can be persuaded.** A CAS gives the same verdict every time, and a confident wrong derivation can't talk it round. Every verdict is also labelled with how it was reached (`exact`, `spot`, `numeric`, `mismatch`, ...), so it can be audited.
3. **Gold labels can be wrong.** That is why every answer here is recomputed independently in `tests/test_problems.py`, and why three are proved in Lean. An eval is only as trustworthy as its answer key.
4. **Cost per correct answer is the number that decides deployments.** Thinking tokens are billed as output, so a model that thinks longer can cost more per problem but less per *correct* problem. The report shows both.

## Quick start

```bash
pip install -r requirements.txt

# No key needed: re-grade the bundled synthetic results and render the report
python run_eval.py --from-results sample_results.jsonl

# Tests (offline, no API calls)
pytest

# Grader self-tests
python grader.py
```

### Live run (makes paid API calls)

```bash
cp .env.example .env          # put your key in .env (git-ignored), or:
export ANTHROPIC_API_KEY=...

python run_eval.py --limit 5                                   # smoke test, default model
python run_eval.py                                             # all 20 problems
python run_eval.py --models claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5
python run_eval.py --effort max --concurrency 8
```

If `ANTHROPIC_API_KEY` is not set, `run_eval.py` prints instructions and exits
with status 0, without making any API call.

| Flag | Default | Meaning |
|---|---|---|
| `--models` | `$EVAL_MODEL` or `claude-opus-5-5` | comma-separated model IDs |
| `--effort` | `high` | `low` / `medium` / `high` / `xhigh` / `max` (`output_config.effort`) |
| `--limit N` | all | only the first N problems |
| `--max-tokens` | 64000 | per-request output cap (thinking + answer) |
| `--concurrency` | 4 | parallel requests |
| `--from-results F` | - | re-grade an existing JSONL and render the report; no API calls |
| `--out`, `--report` | `results/run-<ts>.jsonl`, `results/report.md` | output paths |

**API details.** Requests use adaptive thinking (`thinking: {"type": "adaptive"}`) with an explicit effort level, and they stream (`get_final_message()`) so long reasoning doesn't hit HTTP timeouts. On models that support it, the server-side refusal fallback (`fallbacks: "default"`) is enabled. If a fallback serves a request, cost is priced at the serving model's rates and the result records `served_model`. Refusals, `max_tokens` truncations and API errors are recorded and count as incorrect. The key is read only from the environment or `.env`.

**Cost.** `cost_usd = input_tokens × input_price + output_tokens × output_price`, using the API-reported `usage` and the list-price table `PRICING` in `run_eval.py` (USD per 1M tokens). Thinking tokens are included in `output_tokens`. Edit the table if prices change. Unknown models report `n/a`.

## Repository layout

```
problems.jsonl              20 problems: id, topic, difficulty, format, statement, answer
grader.py                   SymPy equivalence grader + self-tests (python grader.py)
run_eval.py                 async runner, cost tracking, markdown report
sample_results.jsonl        SYNTHETIC results (60 rows: 3 models x 20 problems)
results/report.md           report rendered from the synthetic sample
scripts/make_sample_results.py   seeded generator for the synthetic sample
lean/                       Lean 4 + Mathlib proofs of NT-01, PRF-02, PRF-03
reviews/strand_logrank/     proof review of two log-rank lemmas (STRAND), exact checks
tests/                      offline pytest suite
```

## Problem set

| Topic | Count | Examples |
|---|---|---|
| Algebra | 4 + 2 proof | power sums of cubic roots (Newton's identities), the exponent-equation trap `b^e = 1`, constrained extrema |
| Number theory | 5 | modular powers, cubic residues mod 1001 via CRT, divisibility tricks, Legendre's formula |
| Combinatorics | 4 + 1 proof | derangements, ballot/Catalan paths, bounded compositions via inclusion-exclusion |
| Calculus | 4 | `∫ ln sin x`, Dalzell's `22/7 - π` integral, series via partial fractions |

Each line of `problems.jsonl` looks like this:

```json
{"id": "CALC-04", "topic": "calculus", "difficulty": "hard", "format": "answer",
 "statement": "Evaluate the integral of x^4 (1 - x)^4 / (1 + x^2) dx from 0 to 1. ...",
 "answer": "22/7 - pi"}
```

`format: "proof"` items ask for a proof *and* a closed form. Only the closed
form is graded automatically. Grading the proof needs a rubric or formalization
(see `lean/README.md`).

**How the gold answers are verified.** `tests/test_problems.py` has one
independent verifier per problem: exhaustive enumeration (derangements of 8,
2^15 subsets, all residues mod 1001), exact rational arithmetic, or SymPy
integration and summation. CALC-02 is the one integral SymPy can't do in closed
form, so it is checked to 40 digits by numerical quadrature. The suite fails if
any stored answer disagrees with its verifier.

## How the grader works

1. **Extraction.** The prompt asks for a final line `FINAL ANSWER: <expr>`. The grader takes the last such line, otherwise the last `\boxed{...}`.
2. **Normalization.** Light LaTeX is converted (`\frac`, `\dfrac`, `\sqrt`, `\pi`, `\ln`, `\cdot`, `\left(...\right)`, `^`). A trailing `z =` and thousands separators are dropped.
3. **Safe parsing.** Model output is untrusted, and SymPy's parser calls `eval`. So input must pass a character and identifier whitelist, is parsed with `evaluate=False`, and powers with an exponent over 10,000 are rejected *before* evaluation (`9**9**9**9` can't hang the grader).
4. **Equivalence**, in this order:
   - `exact`: `simplify(pred - gold) == 0`;
   - `spot`: for answers in `n`, exact equality at n = 1..8;
   - `numeric`: agreement within 1e-25 at 50 significant digits, for constants SymPy can't simplify.

   Decimals are rationalized first, so a truncated decimal never matches an irrational gold answer.

## Results

> The table below comes from **synthetic sample data** (`sample_results.jsonl`,
> produced by `scripts/make_sample_results.py`). It demonstrates the report
> format and cost accounting only. These are **not** measured model results.
> Run `python run_eval.py --models ...` with an API key to replace it.

| Model | Accuracy | Total cost | Cost / correct | Mean output tokens |
|---|---|---|---|---|
| `claude-opus-5-5` | _your run_ | _your run_ | _your run_ | _your run_ |
| `claude-sonnet-5-5` | _your run_ | _your run_ | _your run_ | _your run_ |
| `claude-haiku-5-5` | _your run_ | _your run_ | _your run_ | _your run_ |

The full synthetic report is in [`results/report.md`](results/report.md). It
has accuracy by topic and difficulty, the grading-method breakdown, and every
miss with its extracted answer next to the gold answer.

## Formal verification (Lean 4)

`lean/MathProofEval.lean` proves NT-01 (`3^2026 mod 1000 = 329`), PRF-02
(sum of cubes, for all `n`) and PRF-03 (telescoping sum, for all `n`, over ℚ).
Build with `cd lean && lake exe cache get && lake build`. These files were
written in a sandbox with no access to the Lean toolchain and have not been
compiled there. See [`lean/README.md`](lean/README.md) for build details and
for why formal proofs raise trust in an eval.

## Limitations

- 20 problems is a demo-sized set. Expect wide confidence intervals: one problem is 5 percentage points.
- Proof items are graded on the closed form only.
- Prices are list prices hard-coded in `PRICING`. Prompt caching and batch discounts are not modelled.
- The problems are classical, so some may appear in training data. The Lean section explains how to make contamination-resistant variants.
