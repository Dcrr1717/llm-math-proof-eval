"""Exact check of two lemmas on the log-rank test for persistence diagrams.

Setting (STRAND-style): K diagrams split into groups A and B; each finite
feature contributes its persistence as an event time; no censoring. With the
grouped Nelson-Aalen estimator, residuals M_i = 1 - Lambda(t_i) and diagram
totals S_k = sum_{i in k} M_i, the lemmas under review claim

  Lemma 1  U = sum_{k in A} S_k  and  sum_k S_k = 0;
  Lemma 2  under uniform relabelling of the diagrams,
           Var(U) = nA nB sum_k S_k^2 / (K (K - 1)).

All arithmetic is exact (fractions.Fraction), so every "==" below is an
identity check, not a tolerance check. U is always computed from the log-rank
definition sum_j (d_Aj - n_Aj d_j / n_j), never from the S_k.

    python reviews/strand_logrank/check_lemmas.py
"""

from __future__ import annotations

import math
import random
from fractions import Fraction
from itertools import combinations, permutations

Feature = tuple[Fraction, int]  # (time, delta): delta = 1 event, 0 right-censored
Diagram = list[Feature]


def pooled(diagrams: list[Diagram]) -> list[Feature]:
    return [f for d in diagrams for f in d]


def event_times(features: list[Feature]) -> list[Fraction]:
    return sorted({t for t, e in features if e})


def nelson_aalen(features: list[Feature], ties: str = "grouped") -> dict[Fraction, Fraction]:
    """Jumps of the Nelson-Aalen estimator, keyed by distinct event time.

    The risk set at tau_j is {i : t_i >= tau_j}. ties="grouped" uses d_j / n_j
    (the estimator in the lemmas); ties="fh" uses the Fleming-Harrington
    correction sum_{r < d_j} 1 / (n_j - r).
    """
    jumps = {}
    for tau in event_times(features):
        n = sum(1 for t, _ in features if t >= tau)
        d = sum(1 for t, e in features if t == tau and e)
        jumps[tau] = Fraction(d, n) if ties == "grouped" else sum(Fraction(1, n - r) for r in range(d))
    return jumps


def cumhaz(jumps: dict[Fraction, Fraction], t: Fraction, left: bool = False) -> Fraction:
    """Lambda(t) = sum_{tau_j <= t} jump_j; left=True gives Lambda(t-) = sum_{tau_j < t}."""
    return sum((j for tau, j in jumps.items() if (tau < t if left else tau <= t)), Fraction(0))


def residuals(features: list[Feature], *, use_delta: bool = False, ties: str = "grouped",
              left: bool = False) -> list[Fraction]:
    """M_i = 1 - Lambda(t_i) as in the lemmas, or delta_i - Lambda(t_i) with use_delta."""
    jumps = nelson_aalen(features, ties)
    return [(e if use_delta else 1) - cumhaz(jumps, t, left) for t, e in features]


def totals(diagrams: list[Diagram], **kw) -> list[Fraction]:
    """S_k: sum over diagram k of residuals computed from the POOLED Nelson-Aalen."""
    res = residuals(pooled(diagrams), **kw)
    out, pos = [], 0
    for d in diagrams:
        out.append(sum(res[pos:pos + len(d)], Fraction(0)))
        pos += len(d)
    return out


def logrank(diagrams: list[Diagram], group_a: set[int]) -> tuple[Fraction, Fraction]:
    """(U, V) from the textbook definitions; group_a holds diagram indices.

    U = sum_j (d_Aj - n_Aj d_j / n_j)
    V = sum_j d_j (n_Aj / n_j)(1 - n_Aj / n_j)(n_j - d_j) / (n_j - 1), terms with n_j = 1 are 0.
    """
    feats = [(t, e, k in group_a) for k, d in enumerate(diagrams) for t, e in d]
    U = V = Fraction(0)
    for tau in event_times([(t, e) for t, e, _ in feats]):
        risk = [(t, e, a) for t, e, a in feats if t >= tau]
        n = len(risk)
        n_a = sum(1 for _, _, a in risk if a)
        d = sum(1 for t, e, _ in risk if t == tau and e)
        d_a = sum(1 for t, e, a in risk if t == tau and e and a)
        U += d_a - Fraction(n_a * d, n)
        if n > 1:
            V += Fraction(d * n_a * (n - n_a) * (n - d), n * n * (n - 1))
    return U, V


def permutation_check(diagrams: list[Diagram], n_a: int, observed: set[int], **kw) -> dict:
    """Enumerate every assignment of n_a diagrams to A; check Lemmas 1 and 2 exactly."""
    K = len(diagrams)
    S = totals(diagrams, **kw)
    assert sum(S) == 0, "Lemma 1: sum_k S_k != 0"
    Us, Vs = [], []
    for A in combinations(range(K), n_a):
        U, V = logrank(diagrams, set(A))
        assert U == sum(S[k] for k in A), f"Lemma 1: U != sum_(k in A) S_k for A = {A}"
        Us.append(U)
        Vs.append(V)
    M = len(Us)
    assert M == math.comb(K, n_a)
    mean = sum(Us) / M
    # The M assignments ARE the permutation distribution: divide by M, not M - 1.
    var_exact = sum(u * u for u in Us) / M - mean**2
    var_ddof1 = sum((u - mean) ** 2 for u in Us) / (M - 1)
    var_formula = Fraction(n_a * (K - n_a), K * (K - 1)) * sum(s * s for s in S)
    assert var_exact == var_formula, "Lemma 2: variance formula fails"
    U_obs, V_obs = logrank(diagrams, observed)
    EV = sum(Vs) / M
    return dict(K=K, N=sum(len(d) for d in diagrams), M=M, S=S, mean=mean, var_exact=var_exact,
                var_ddof1=var_ddof1, var_formula=var_formula, U_obs=U_obs, V_obs=V_obs,
                # kappa is 0/0 (None) when every event time is a single tied block: V = Var(U) = 0
                kappa=var_formula / V_obs if V_obs else None, EV=EV,
                kappa_bar=var_formula / EV if EV else None,
                p_two=Fraction(sum(1 for u in Us if abs(u) >= abs(U_obs)), M), Us=Us)


def make_diagrams(seed: int, sizes: list[int], ties: bool) -> list[Diagram]:
    """Random diagrams with a per-diagram scale, i.e. dependence within a diagram.

    Persistences are scale_k * Exp(1). Without ties they are rounded to 1e-6
    (distinctness is asserted); with ties they are rounded UP to integers, which
    produces many tied values. All features are events (delta = 1).
    """
    rng = random.Random(seed)
    diagrams = []
    for m in sizes:
        scale = rng.choice([0.5, 1.0, 3.0])
        draws = [scale * rng.expovariate(1.0) for _ in range(m)]
        if ties:
            ps = [Fraction(max(1, math.ceil(x))) for x in draws]
        else:
            ps = [Fraction(max(1, round(x * 10**6)), 10**6) for x in draws]
        diagrams.append([(p, 1) for p in ps])
    if not ties:
        times = [t for t, _ in pooled(diagrams)]
        assert len(set(times)) == len(times), "unexpected tie; change the seed"
    return diagrams


def fmt(x: Fraction) -> str:
    return f"{float(x):.6f}"


def fracs(xs: list[Fraction]) -> str:
    return "[" + ", ".join(str(x) for x in xs) + "]"


def report(title: str, r: dict) -> None:
    print(f"\n=== {title} ===")
    print(f"K = {r['K']}, N = {r['N']}, asignaciones = {r['M']}")
    print("S_k =", ", ".join(f"{float(s):+.4f}" for s in r["S"]), f"  (suma = {sum(r['S'])})")
    print(f"Lema 1: U == sum_(k in A) S_k en las {r['M']} asignaciones (exacto): OK")
    print(f"E_perm[U]                        = {r['mean']}")
    print(f"Var_perm(U) por enumeracion      = {fmt(r['var_exact'])}")
    print(f"nA nB sum S^2 / (K(K-1))         = {fmt(r['var_formula'])}   iguales: {r['var_exact'] == r['var_formula']}")
    print(f"(error tipico: dividir entre M-1 = {fmt(r['var_ddof1'])}, factor M/(M-1))")
    print(f"U_obs = {fmt(r['U_obs'])}, V_obs (hipergeometrica) = {fmt(r['V_obs'])}")
    print(f"kappa = Var(U)/V_obs = {fmt(r['kappa'])};  E_perm[V] = {fmt(r['EV'])};  "
          f"kappa_bar = Var(U)/E_perm[V] = {fmt(r['kappa_bar'])}")
    print(f"p bilateral exacto por permutacion = {r['p_two']} = {float(r['p_two']):.4f}")


def edge_cases() -> None:
    F, one = Fraction, 1
    print("\n=== Casos limite y contraejemplos ===")

    # (a) Censoring: with 1 - Lambda the identities fail; with delta - Lambda they hold.
    dg = [[(F(1), 1)], [(F(2), 0)]]
    U, _ = logrank(dg, {1})
    naive, mart = totals(dg), totals(dg, use_delta=True)
    print(f"(a) censura, t = (1 evento, 2 censurado), A = {{2}}: U = {U}; "
          f"sum_A(1 - Lambda) = {naive[1]}; sum_k(1 - Lambda) = {sum(naive)}; "
          f"con delta - Lambda: sum_A = {mart[1]}, sum_k = {sum(mart)}")
    assert U == -F(1, 2) and naive[1] == F(1, 2) and sum(naive) == 1
    assert mart[1] == U and sum(mart) == 0

    # (b) Ties with the Fleming-Harrington increment instead of d_j / n_j.
    dg = [[(F(1), 1)], [(F(1), 1)]]
    U, _ = logrank(dg, {0})
    fh = totals(dg, ties="fh")
    print(f"(b) empate t = (1, 1), A = {{1}}: U = {U}; Nelson-Aalen agrupado: S = {fracs(totals(dg))}; "
          f"Fleming-Harrington: S = {fracs(fh)}, suma = {sum(fh)}")
    assert U == 0 and totals(dg) == [0, 0] and fh == [-F(1, 2), -F(1, 2)]

    # (c) Left-continuous Lambda(t_i-) instead of Lambda(t_i).
    dg = [[(F(1), 1)], [(F(2), 1)]]
    U, _ = logrank(dg, {0})
    lc = totals(dg, left=True)
    print(f"(c) t = (1, 2), A = {{1}}: U = {U}; con Lambda(t-): S = {fracs(lc)}, suma = {sum(lc)}")
    assert U == F(1, 2) and lc == [1, F(1, 2)]

    # (d) m_k = 1: diagram permutation = feature permutation, and Var_perm(U) = E_perm[V] exactly.
    for ties in (False, True):
        dg = make_diagrams(7, [one] * 8, ties)
        r = permutation_check(dg, 4, {0, 1, 2, 3})
        assert r["var_formula"] == r["EV"]
        print(f"(d) m_k = 1, K = 8, {'con' if ties else 'sin'} empates: Var_perm(U) = {fmt(r['var_formula'])}"
              f" = E_perm[V] = {fmt(r['EV'])} (exacto); V_obs = {fmt(r['V_obs'])}, kappa = {fmt(r['kappa'])}")

    # (e) Empty diagrams (m_k = 0) are allowed: S_k = 0, and they still count in K.
    dg = make_diagrams(11, [3, 0, 2, 4, 1, 5, 0, 3], ties=False)
    r = permutation_check(dg, 4, {0, 1, 2, 3})
    assert r["S"][1] == r["S"][6] == 0
    print(f"(e) diagramas 2 y 7 vacios: S = {', '.join(f'{float(s):+.4f}' for s in r['S'])}; lemas 1 y 2 exactos: OK")

    # (f) Censoring handled with delta - Lambda: both lemmas still hold exactly.
    rng = random.Random(5)
    dg = [[(t, int(rng.random() < 0.7)) for t, _ in d] for d in make_diagrams(5, [3, 2, 4, 1, 3, 2, 5, 2], True)]
    r = permutation_check(dg, 4, {0, 1, 2, 3}, use_delta=True)
    print(f"(f) con censura y residuos delta - Lambda: lemas 1 y 2 exactos (Var = {fmt(r['var_formula'])}): OK")

    # (g) Small K: the permutation distribution is coarse; U(A^c) = -U(A) when nA = nB.
    dg = make_diagrams(3, [2, 3, 1, 2], ties=False)
    r = permutation_check(dg, 2, {0, 1})
    us = sorted(float(u) for u in r["Us"])
    print(f"(g) K = 4, nA = nB = 2: los 6 valores de U = {[round(u, 4) for u in us]}; "
          f"p bilateral minimo = 2/6 = 1/3; con K = 8 (4+4) es 2/70 = {2 / 70:.4f}")

    # (h) All persistences tied: every residual is 0, so V = Var(U) = 0 and kappa = 0/0.
    dg = [[(F(1), 1)] * 3, [(F(1), 1)], [(F(1), 1)] * 2]
    r = permutation_check(dg, 1, {0})
    assert r["V_obs"] == r["var_formula"] == 0 and r["kappa"] is None
    print("(h) todas las persistencias empatadas (t = 1): V = Var(U) = 0, kappa = 0/0 indefinido")

    # (i) Equal m_k = m: kappa_0 = (N-1) sum S^2 / ((K-1) m sum M^2) has mean exactly 1
    #     over all allocations of the N features to the K diagrams (feature exchangeability).
    times = [(F(t), 1) for t in (1, 2, 2, 3, 5, 8)]
    N, K, m = 6, 3, 2
    res = residuals(times)  # the pooled Nelson-Aalen does not depend on the allocation
    Q = sum(x * x for x in res)
    # unordered partitions of the feature indices into K blocks of size m (all equally likely)
    parts = {frozenset(frozenset(p[m * k:m * k + m]) for k in range(K)) for p in permutations(range(N))}
    k0 = [(N - 1) * sum(sum(res[i] for i in b) ** 2 for b in p) / ((K - 1) * m * Q) for p in parts]
    mean_k0 = sum(k0) / len(k0)
    print(f"(i) m_k = 2, K = 3, t = (1,2,2,3,5,8): media de kappa_0 sobre las {len(parts)} particiones = {mean_k0}"
          f" (rango {fmt(min(k0))} a {fmt(max(k0))})")
    assert len(parts) == 15 and mean_k0 == 1


def main() -> None:
    sizes = [3, 5, 2, 4, 1, 6, 3, 4]  # m_k, unequal on purpose (one m_k = 1)
    observed = {0, 1, 2, 3}           # diagrams 1-4 in A, 5-8 in B
    report("Caso 1: K = 8, sin empates", permutation_check(make_diagrams(2026, sizes, False), 4, observed))
    report("Caso 2: K = 8, con empates", permutation_check(make_diagrams(2026, sizes, True), 4, observed))
    edge_cases()
    print("\nTodas las comprobaciones exactas pasaron.")


if __name__ == "__main__":
    main()
