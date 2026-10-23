# Lean 4 formal verification

`MathProofEval.lean` proves, in Lean 4 over Mathlib, that three gold answers in
`../problems.jsonl` are correct:

| Problem | Statement proved | Theorem |
|---|---|---|
| NT-01 | `3 ^ 2026 % 1000 = 329` | `MathProofEval.nt01_last_three_digits` |
| PRF-02 | `4 * ∑_{i ≤ n} i^3 = (n(n+1))^2` for every `n : ℕ`, and the ℚ form `∑ i^3 = n^2 (n+1)^2 / 4` | `sum_cubes`, `sum_cubes_closed_form` |
| PRF-03 | `∑_{k=1}^{n} 1/(k(k+1)) = n/(n+1)` over ℚ for every `n` | `telescoping` |

## Build

```bash
# needs elan (https://github.com/leanprover/elan)
cd lean
lake exe cache get   # download prebuilt Mathlib oleans
lake build
```

The project pins `leanprover/lean4:v4.15.0` and the matching Mathlib tag
`v4.15.0`. To move to a newer Mathlib, set `rev` in `lakefile.toml` to its tag
and copy that tag's `lean-toolchain` file here.

**Build status:** these files were written in a sandbox whose network policy
blocks the Lean release servers, so they have **not** been compiled there.
They build with `lake build` on a machine with the toolchain and Mathlib.
Any proof step that breaks under a different Mathlib version is a version
issue, not a problem with the mathematics. The same answers are also checked
independently in Python (`tests/test_problems.py`).

## What formal verification adds to eval trust

A verifier-backed eval has two possible points of failure. The **grader**
can mis-judge equivalence. The **gold label** can be wrong, and then every
model gets graded against an error. SymPy deals with the first. Lean deals
with the second:

- **Gold labels become theorems.** `n/(n+1)` is not just "what the answer key
  says". The kernel has checked that it equals the sum for *every* natural
  number `n`. Spot checks at n = 1..8 or a CAS `simplify` can't give that
  guarantee.
- **The trusted base is small.** Lean's kernel checks the proof term. You
  don't have to trust the tactic that found the proof, or the author's
  algebra.
- **A path to grading proofs, not just answers.** On `format: "proof"` items,
  the Python pipeline only grades the closed form. If a model's proof can be
  turned into Lean (by hand or by autoformalization), the kernel can accept
  or reject the argument itself. That is a binary, reproducible signal, with
  no rubric and no grader drift.
- **Contamination-resistant variants.** Once an identity is a parametric
  theorem, you can generate new instances (other exponents, other moduli) and
  their labels stay correct by construction.
