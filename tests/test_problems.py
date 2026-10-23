"""Independently re-derive every gold answer in problems.jsonl.

Each check below computes the answer from scratch (brute force, exact
arithmetic, or SymPy CAS) and compares it with the stored canonical answer
using the grader. A wrong gold label fails the suite.
"""

import json
from functools import lru_cache
from itertools import permutations, product
from math import factorial
from pathlib import Path

import pytest
import sympy as sp

from grader import check_equivalence, parse_answer

ROOT = Path(__file__).resolve().parents[1]
PROBLEMS = [json.loads(l) for l in (ROOT / "problems.jsonl").read_text().splitlines() if l.strip()]
BY_ID = {p["id"]: p for p in PROBLEMS}
x, n, k = sp.symbols("x n k")


def alg01():
    cands = set()
    for eq in (x**2 - 5 * x + 4, x**2 - 9 * x + 20, x**2 - 5 * x + 6):
        cands |= set(sp.solve(eq, x))
    sols = set()
    for c in cands:
        base, ex = c**2 - 5 * c + 5, c**2 - 9 * c + 20
        if base == 1 or (ex == 0 and base != 0) or (base == -1 and ex % 2 == 0):
            sols.add(c)
    # b^e = 1 over the reals: b = 1; or e = 0 with b != 0; or b = -1 with e an even integer.
    return sum(sols)


def alg02():
    # Newton's identities from the coefficients of x^3 - 3x + 1.
    e1, e2, e3 = 0, -3, -1
    p = [3, e1]
    p.append(e1 * p[1] - 2 * e2)
    for m in range(3, 6):
        p.append(e1 * p[m - 1] - e2 * p[m - 2] + e3 * p[m - 3])
    numeric = sum(r**5 for r in sp.Poly(x**3 - 3 * x + 1).nroots(n=40))
    assert abs(numeric - p[5]) < 1e-30
    return p[5]


def alg03():
    z = sp.Symbol("z", real=True)
    # x, y real roots of t^2 - (6 - z) t + (9 - z(6 - z)): discriminant >= 0.
    region = sp.solve_univariate_inequality((6 - z) ** 2 - 4 * (9 - z * (6 - z)) >= 0, z, relational=False)
    return region.sup


def alg04():
    return sum(sp.Rational(1, i * (i + 1) * (i + 2)) for i in range(1, 101))


def nt01():
    return pow(3, 2026, 1000)


def nt02():
    return sum(1 for t in range(0, 1001) if pow(t, 3, 1001) == 1)


def nt03():
    # n + 10 | n^3 + 100  <=>  n + 10 | 900, so n <= 890; search well beyond.
    return max(m for m in range(1, 20_000) if (m**3 + 100) % (m + 10) == 0)


def nt04():
    f, z = factorial(2026), 0
    while f % 10 == 0:
        f //= 10
        z += 1
    return z


def nt05():
    # x > 60 and y = 60x/(x-60) is a positive integer; x ranges up to 60 + 3600.
    return sum(1 for a in range(61, 60 + 3600 + 1) if (60 * a) % (a - 60) == 0)


def comb01():
    return sum(1 for p in permutations(range(8)) if all(p[i] != i for i in range(8)))


def comb02():
    @lru_cache(None)
    def paths(a, b):
        if b > a:
            return 0
        if a == 0 and b == 0:
            return 1
        return (paths(a - 1, b) if a else 0) + (paths(a, b - 1) if b else 0)

    return paths(6, 6)


def comb03():
    return sum(1 for s in range(2**15) if s & (s >> 1) == 0)


def comb04():
    return sum(1 for t in product(range(8), repeat=4) if sum(t) == 20)


def calc01():
    return sp.integrate(x**2 * sp.exp(-x) * sp.sin(x), (x, 0, sp.oo))


def calc02():
    # SymPy cannot do this integral symbolically; verify the classical value to 40 digits.
    val = sp.Integral(sp.log(sp.sin(x)), (x, 0, sp.pi / 2)).evalf(45)
    closed = -sp.pi * sp.log(2) / 2
    assert abs(val - closed.evalf(45)) < sp.Float("1e-40")
    return closed


def calc03():
    return sp.summation(1 / (k**2 * (k + 1)), (k, 1, sp.oo))


def calc04():
    return sp.integrate(x**4 * (1 - x) ** 4 / (1 + x**2), (x, 0, 1))


def prf01():
    for m in range(1, 15):
        assert sum(j * sp.binomial(m, j) for j in range(m + 1)) == m * 2 ** (m - 1)
    return sp.summation(k * sp.binomial(n, k), (k, 0, n)).args[0][0]  # Piecewise branch for n > 0


def prf02():
    return sp.factor(sp.summation(k**3, (k, 1, n)))


def prf03():
    return sp.simplify(sp.summation(1 / (k * (k + 1)), (k, 1, n)))


VERIFIERS = {
    "ALG-01": alg01, "ALG-02": alg02, "ALG-03": alg03, "ALG-04": alg04,
    "NT-01": nt01, "NT-02": nt02, "NT-03": nt03, "NT-04": nt04, "NT-05": nt05,
    "COMB-01": comb01, "COMB-02": comb02, "COMB-03": comb03, "COMB-04": comb04,
    "CALC-01": calc01, "CALC-02": calc02, "CALC-03": calc03, "CALC-04": calc04,
    "PRF-01": prf01, "PRF-02": prf02, "PRF-03": prf03,
}


def test_problem_schema():
    assert 15 <= len(PROBLEMS) <= 20
    assert len(BY_ID) == len(PROBLEMS), "duplicate ids"
    required = {"id", "topic", "difficulty", "format", "statement", "answer"}
    for p in PROBLEMS:
        assert required <= p.keys()
        assert p["topic"] in {"algebra", "number_theory", "combinatorics", "calculus"}
        assert p["difficulty"] in {"easy", "medium", "hard"}
        assert p["format"] in {"answer", "proof"}
        assert p["statement"].isascii() or "≡" in p["statement"]
        assert parse_answer(p["answer"]) is not None, p["id"]


def test_every_problem_has_an_independent_verifier():
    assert set(VERIFIERS) == set(BY_ID)


@pytest.mark.parametrize("pid", sorted(BY_ID))
def test_gold_answer_is_correct(pid):
    computed = sp.sympify(VERIFIERS[pid]())
    ok, _ = check_equivalence(computed, parse_answer(BY_ID[pid]["answer"]))
    assert ok, (pid, computed)


def test_spot_check_closed_forms_numerically():
    # Sanity on the n-dependent answers at concrete n, independent of SymPy summation.
    for m in range(1, 12):
        assert sum(sp.Rational(j**3) for j in range(1, m + 1)) == parse_answer(BY_ID["PRF-02"]["answer"]).subs(n, m)
        assert sum(sp.Rational(1, j * (j + 1)) for j in range(1, m + 1)) == parse_answer(BY_ID["PRF-03"]["answer"]).subs(n, m)
