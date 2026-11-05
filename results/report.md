# Math eval report

- Source: `run-20261102T191157Z.jsonl`
- Generated: 2026-11-02 19:11 UTC
- Problems per model: 20; effort: high
- Grading: SymPy symbolic equivalence (`grader.py`); cost from API-reported token usage at list prices (`PRICING` in `run_eval.py`).

## Summary

| Model | Accuracy | Correct | Total cost | Cost / correct | Mean output tokens | Mean latency | Failed calls* |
|---|---|---|---|---|---|---|---|
| `claude-haiku-5-5` | 100% | 20/20 | $0.0089 | $0.0004 | 853 | 3.8s | 0 |
| `claude-sonnet-5-5` | 100% | 20/20 | $0.0916 | $0.0046 | 419 | 3.5s | 0 |
| `claude-opus-5-5` | 100% | 20/20 | $0.2861 | $0.0143 | 676 | 5.9s | 0 |

\* refusals, `max_tokens` truncations and API errors; these count as incorrect.

## Accuracy by topic

| topic | claude-haiku-5-5 | claude-sonnet-5-5 | claude-opus-5-5 |
|---|---|---|---|
| algebra | 6/6 | 6/6 | 6/6 |
| calculus | 4/4 | 4/4 | 4/4 |
| combinatorics | 5/5 | 5/5 | 5/5 |
| number_theory | 5/5 | 5/5 | 5/5 |

## Accuracy by difficulty

| difficulty | claude-haiku-5-5 | claude-sonnet-5-5 | claude-opus-5-5 |
|---|---|---|---|
| easy | 5/5 | 5/5 | 5/5 |
| medium | 11/11 | 11/11 | 11/11 |
| hard | 4/4 | 4/4 | 4/4 |

## How answers were graded

| Method | Count |
|---|---|
| exact | 60 |

## Incorrect or failed items

None.
