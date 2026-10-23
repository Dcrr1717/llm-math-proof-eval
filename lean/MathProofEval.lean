/-
  Formal verification of gold answers from `problems.jsonl` (Lean 4 + Mathlib).

  The Python grader checks that a model's answer is equivalent to the gold
  answer. These theorems check that the gold answers themselves are true,
  for all `n` rather than for the finitely many values a test can try.

    NT-01   3^2026 mod 1000 = 329                 nt01_last_three_digits
    PRF-02  1^3 + ... + n^3 = n^2 (n+1)^2 / 4     sum_cubes, sum_cubes_closed_form
    PRF-03  Σ_{k=1}^{n} 1/(k(k+1)) = n/(n+1)       telescoping
-/
import Mathlib

open Finset

namespace MathProofEval

/-- NT-01: the last three digits of 3^2026 are 329. -/
theorem nt01_last_three_digits : 3 ^ 2026 % 1000 = 329 := by
  norm_num

/-- PRF-02 over ℕ, division-free: 4 · Σ_{i=0}^{n} i^3 = (n(n+1))^2. -/
theorem sum_cubes (n : ℕ) :
    4 * ∑ i ∈ range (n + 1), i ^ 3 = (n * (n + 1)) ^ 2 := by
  induction n with
  | zero => simp
  | succ k ih =>
    rw [sum_range_succ, mul_add, ih]
    ring

/-- PRF-02 in the exact form of the gold answer `n**2*(n+1)**2/4`, over ℚ. -/
theorem sum_cubes_closed_form (n : ℕ) :
    (∑ i ∈ range (n + 1), (i : ℚ) ^ 3) = (n : ℚ) ^ 2 * ((n : ℚ) + 1) ^ 2 / 4 := by
  have h : ((4 * ∑ i ∈ range (n + 1), i ^ 3 : ℕ) : ℚ) = ((n * (n + 1)) ^ 2 : ℕ) := by
    rw [sum_cubes]
  push_cast at h
  linear_combination h / 4

/-- PRF-03: Σ_{k=1}^{n} 1/(k(k+1)) = n/(n+1), written with k ↦ k+1 over `range n`. -/
theorem telescoping (n : ℕ) :
    ∑ k ∈ range n, (1 : ℚ) / (((k : ℚ) + 1) * ((k : ℚ) + 2)) = (n : ℚ) / ((n : ℚ) + 1) := by
  induction n with
  | zero => simp
  | succ m ih =>
    rw [sum_range_succ, ih]
    have h1 : (m : ℚ) + 1 ≠ 0 := by positivity
    have h2 : (m : ℚ) + 2 ≠ 0 := by positivity
    have h3 : (m : ℚ) + 1 + 1 ≠ 0 := by positivity
    push_cast
    field_simp
    ring

end MathProofEval
