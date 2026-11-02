"""Exact checks of the STRAND log-rank lemmas on many random diagram sets.

See reviews/strand_logrank/REVIEW.md. Every assertion is an identity in
rational arithmetic, checked over all C(K, nA) diagram assignments.
"""

import random
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reviews" / "strand_logrank"))

from check_lemmas import (  # noqa: E402
    edge_cases,
    logrank,
    make_diagrams,
    permutation_check,
    residuals,
    totals,
)


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("ties", [False, True])
def test_lemmas_hold_exactly(seed, ties):
    rng = random.Random(seed)
    K = rng.randint(2, 8)
    n_a = rng.randint(1, K - 1)
    sizes = [rng.randint(0, 5) for _ in range(K)]
    sizes[0] = max(sizes[0], 1)  # at least one event
    # permutation_check asserts Lemma 1 for every assignment and Lemma 2 for the distribution
    r = permutation_check(make_diagrams(seed, sizes, ties), n_a, set(range(n_a)))
    assert r["mean"] == 0
    assert r["var_exact"] == r["var_formula"]


@pytest.mark.parametrize("seed", range(6))
def test_single_feature_diagrams_variance_equals_mean_hypergeometric(seed):
    r = permutation_check(make_diagrams(seed, [1] * 7, ties=seed % 2 == 1), 3, {0, 1, 2})
    assert r["var_formula"] == r["EV"]


@pytest.mark.parametrize("seed", range(6))
def test_censoring_needs_delta_residuals(seed):
    rng = random.Random(100 + seed)
    dg = [[(t, int(rng.random() < 0.6)) for t, _ in d] for d in make_diagrams(seed, [2, 3, 1, 4, 2, 3], True)]
    if all(e for d in dg for _, e in d):
        dg[0][0] = (dg[0][0][0], 0)
    # delta_i - Lambda(t_i): both lemmas survive censoring
    permutation_check(dg, 3, {0, 1, 2}, use_delta=True)
    # 1 - Lambda(t_i): the residuals no longer sum to zero
    n_censored = sum(1 for d in dg for _, e in d if not e)
    assert sum(totals(dg)) == n_censored


def test_textbook_counterexamples():
    F = Fraction
    # censored feature in A: U = -1/2 but sum_A (1 - Lambda) = +1/2
    dg = [[(F(1), 1)], [(F(2), 0)]]
    assert logrank(dg, {1})[0] == -F(1, 2) and totals(dg)[1] == F(1, 2)
    # Fleming-Harrington ties break sum M_i = 0
    assert sum(residuals([(F(1), 1), (F(1), 1)], ties="fh")) == -1
    # Lambda(t-) instead of Lambda(t) breaks it too
    assert sum(residuals([(F(1), 1), (F(2), 1)], left=True)) == F(3, 2)


def test_edge_case_script_runs(capsys):
    edge_cases()
    assert "(i)" in capsys.readouterr().out
