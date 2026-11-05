# Proof benchmark (private items)

22 items from peer-reviewed papers; proofs graded blind against the published key steps. Score per proof: correct 1, minor gaps 0.75, major gap 0.25, wrong 0, averaged over judge repeats.

| Model | Proofs | Mean score | Fully correct | Unfinished | Solve cost | Cost per proof |
|---|---|---|---|---|---|---|
| claude-haiku-5-5 | 22 | 0.59 | 13/22 | 9 | $0.52 | $0.024 |
| claude-opus-5-5 | 22 | 0.95 | 21/22 | 1 | $6.49 | $0.295 |
| claude-sonnet-5-5 | 22 | 0.86 | 19/22 | 3 | $4.08 | $0.185 |

Judge consistency: identical verdict on 53/53 proofs judged more than once.

| Model | Mean score, arXiv v1 before 2026-01-01 | on or after |
|---|---|---|
| claude-haiku-5-5 | 0.62 (n=21) | 0.00 (n=1) |
| claude-opus-5-5 | 0.95 (n=21) | 1.00 (n=1) |
| claude-sonnet-5-5 | 0.86 (n=21) | 1.00 (n=1) |

## Second judge (claude-sonnet-5-5)

Independent judge over the same proofs, 53 calls, $1.97. Same verdict as the primary judge (claude-opus-5-5) on 53/53 proofs (100%).

| Model | Mean score (claude-opus-5-5) | Mean score (claude-sonnet-5-5) |
|---|---|---|
| claude-haiku-5-5 | 1.00 (n=13) | 1.00 (n=13) |
| claude-opus-5-5 | 1.00 (n=21) | 1.00 (n=21) |
| claude-sonnet-5-5 | 1.00 (n=19) | 1.00 (n=19) |

No disagreements. Every finished proof got `correct` from both judges, so this agreement says nothing about how strict the judges are; the score differences between models come only from unfinished (truncated) answers.

Per-proof verdicts of both judges: `proof_bench_report_second_judge.jsonl`.
