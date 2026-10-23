"""SymPy-backed final-answer grader for math evaluations.

The grader turns a model's free-text response into a SymPy expression and
decides whether it is mathematically equivalent to a gold answer. Different
forms of the same value are accepted: ``1/2``, ``0.5``, ``\\frac{1}{2}``,
``-\\frac{\\pi \\ln 2}{2}`` and ``-pi*log(2)/2`` all compare as you would expect.

Pipeline
--------
1. ``extract_final_answer`` pulls the candidate out of the response: the last
   ``FINAL ANSWER:`` line, otherwise the last ``\\boxed{...}``.
2. ``parse_answer`` normalises light LaTeX, checks the string against a token
   whitelist (model output is untrusted and SymPy parsing uses ``eval``),
   parses it without evaluation, rejects huge powers, then evaluates.
3. ``check_equivalence`` tries, in order:
     * ``exact``   - ``simplify(pred - gold) == 0``;
     * ``spot``    - for answers with free variables (e.g. ``n``), exact
                     equality at n = 1..8;
     * ``numeric`` - for constants SymPy can't simplify, agreement to 1e-25
                     at 50 significant digits.
   Decimal answers are converted to exact rationals first, so ``0.5`` matches
   ``1/2`` but ``-1.0888`` does not match ``-pi*log(2)/2``.

Run ``python grader.py`` to execute the built-in self-tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    rationalize,
    standard_transformations,
)

MAX_ANSWER_CHARS = 200
MAX_EXPONENT = 10_000
NUMERIC_DIGITS = 50
NUMERIC_TOL = sp.Float("1e-25", NUMERIC_DIGITS)
SPOT_VALUES = range(1, 9)

_TRANSFORMS = standard_transformations + (
    convert_xor,
    rationalize,
    implicit_multiplication_application,
)

_SYMBOLS = {name: sp.Symbol(name) for name in ("n", "x", "y", "z", "k", "m")}
_FUNCS = {
    "sqrt": sp.sqrt,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "binomial": sp.binomial,
    "factorial": sp.factorial,
}
_CONSTS = {"pi": sp.pi, "e": sp.E, "E": sp.E, "oo": sp.oo, "I": sp.I}
_LOCALS = {**_SYMBOLS, **_FUNCS, **_CONSTS}
_ALLOWED_IDENTIFIERS = set(_LOCALS)
# Only the SymPy names the parser itself emits; no Python builtins are exposed.
_GLOBALS = {
    "__builtins__": {},
    "Integer": sp.Integer,
    "Rational": sp.Rational,
    "Float": sp.Float,
    "Symbol": sp.Symbol,
    "Add": sp.Add,
    "Mul": sp.Mul,
    "Pow": sp.Pow,
}

_LATEX_REPLACEMENTS = [
    (r"\\left|\\right|\\displaystyle|\\,|\\;|\\!|\\ ", ""),
    (r"\\cdot|\\times", "*"),
    (r"\\pi", " pi "),
    (r"\\ln", " log "),
    (r"\\log", " log "),
    (r"\\exp", " exp "),
    (r"\\sin", " sin "),
    (r"\\cos", " cos "),
    (r"\\tan", " tan "),
    (r"\\infty", " oo "),
]


@dataclass(frozen=True)
class GradeResult:
    correct: bool
    method: str  # exact | spot | numeric | mismatch | unparseable | no_answer
    extracted: str | None
    detail: str = ""


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _last_boxed(text: str) -> str | None:
    """Return the content of the last ``\\boxed{...}``, honouring nested braces."""
    start = text.rfind("\\boxed{")
    if start == -1:
        return None
    i = start + len("\\boxed{")
    depth = 1
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j]
    return None


def extract_final_answer(response: str) -> str | None:
    """Pull the final answer string out of a model response."""
    if not response:
        return None
    matches = re.findall(r"FINAL ANSWER\s*[:：]\s*(.+)", response, flags=re.IGNORECASE)
    if matches:
        candidate = matches[-1].strip()
        boxed = _last_boxed(candidate)
        return boxed.strip() if boxed is not None else candidate
    boxed = _last_boxed(response)
    return boxed.strip() if boxed is not None else None


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def _replace_frac(s: str) -> str:
    """Rewrite ``\\frac{a}{b}`` (and dfrac/tfrac) as ``((a)/(b))``, innermost first."""
    pattern = re.compile(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}")
    while True:
        new = pattern.sub(r"((\1)/(\2))", s)
        if new == s:
            return new
        s = new


def normalize(answer: str) -> str:
    s = answer.strip()
    s = s.strip("$").strip()
    s = re.sub(r"\\boxed\{(.*)\}", r"\1", s)
    s = re.sub(r"\\text\{[^{}]*\}", "", s)
    s = s.rstrip(".").strip()
    # "z = 4" or "S_n = n/(n+1)": keep the right-hand side.
    if "=" in s:
        s = s.split("=")[-1].strip()
    for pat, rep in _LATEX_REPLACEMENTS:
        s = re.sub(pat, rep, s)
    s = _replace_frac(s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", s)
    s = s.replace("{", "(").replace("}", ")")
    s = s.replace("−", "-").replace("·", "*").replace("π", "pi")
    s = s.replace("\\", " ")
    # Thousands separators: "14,833" -> "14833".
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    return " ".join(s.split())


def _is_safe(s: str) -> bool:
    if len(s) > MAX_ANSWER_CHARS:
        return False
    if not re.fullmatch(r"[0-9A-Za-z_+\-*/^()., ]*", s):
        return False
    return all(tok in _ALLOWED_IDENTIFIERS for tok in re.findall(r"[A-Za-z_]+", s))


def _has_huge_power(expr: sp.Basic) -> bool:
    for node in sp.preorder_traversal(expr):
        if isinstance(node, sp.Pow):
            exp = node.exp
            if exp.is_number and exp.is_real and abs(exp) > MAX_EXPONENT:
                return True
    return False


def parse_answer(answer: str | None) -> sp.Expr | None:
    """Parse an answer string into a SymPy expression; ``None`` if unsafe/invalid."""
    if answer is None:
        return None
    s = normalize(answer)
    if not s or not _is_safe(s):
        return None
    try:
        raw = parse_expr(
            s,
            local_dict=dict(_LOCALS),
            global_dict=dict(_GLOBALS),
            transformations=_TRANSFORMS,
            evaluate=False,
        )
        if not isinstance(raw, sp.Basic) or _has_huge_power(raw):
            return None
        return sp.sympify(raw).doit()
    except Exception:  # noqa: BLE001 - any parse failure means "unparseable"
        return None


# --------------------------------------------------------------------------
# Equivalence
# --------------------------------------------------------------------------

def _exact_equal(a: sp.Expr, b: sp.Expr) -> bool:
    try:
        return sp.simplify(a - b) == 0
    except Exception:  # noqa: BLE001
        return False


def check_equivalence(pred: sp.Expr, gold: sp.Expr) -> tuple[bool, str]:
    if _exact_equal(pred, gold):
        return True, "exact"

    free = sorted((pred.free_symbols | gold.free_symbols), key=str)
    if free:
        if not set(pred.free_symbols) <= set(gold.free_symbols):
            return False, "mismatch"
        for v in SPOT_VALUES:
            subs = {s: v for s in free}
            if not _exact_equal(pred.subs(subs), gold.subs(subs)):
                return False, "mismatch"
        return True, "spot"

    try:
        pv = sp.N(pred, NUMERIC_DIGITS)
        gv = sp.N(gold, NUMERIC_DIGITS)
        if pv.is_number and gv.is_number:
            scale = max(sp.Float(1), abs(gv))
            if abs(pv - gv) / scale < NUMERIC_TOL:
                return True, "numeric"
    except Exception:  # noqa: BLE001
        pass
    return False, "mismatch"


def grade(response: str, gold_answer: str) -> GradeResult:
    """Grade a full model response against a gold answer string."""
    gold = parse_answer(gold_answer)
    if gold is None:
        raise ValueError(f"gold answer does not parse: {gold_answer!r}")
    extracted = extract_final_answer(response)
    if extracted is None:
        return GradeResult(False, "no_answer", None, "no FINAL ANSWER line or \\boxed{}")
    pred = parse_answer(extracted)
    if pred is None:
        return GradeResult(False, "unparseable", extracted)
    ok, method = check_equivalence(pred, gold)
    return GradeResult(ok, method, extracted, f"pred={pred} gold={gold}")


def answers_equivalent(pred: str, gold: str) -> bool:
    """Convenience wrapper: compare two bare answer strings."""
    p, g = parse_answer(pred), parse_answer(gold)
    if p is None or g is None:
        return False
    return check_equivalence(p, g)[0]


# --------------------------------------------------------------------------
# Self-tests
# --------------------------------------------------------------------------

SELF_TESTS: list[tuple[str, str, bool]] = [
    ("1/2", "0.5", True),
    ("1/2", r"\frac{1}{2}", True),
    ("2575/10302", r"\dfrac{2575}{10302}", True),
    ("-pi*log(2)/2", r"-\frac{\pi \ln 2}{2}", True),
    ("-pi*log(2)/2", "-pi/2*ln(2)", True),
    ("-pi*log(2)/2", "log(2**(-pi/2))", True),
    ("-pi*log(2)/2", "-1.0887930451518", False),
    ("pi**2/6 - 1", r"\frac{\pi^2}{6}-1", True),
    ("pi**2/6 - 1", r"\frac{\pi^2 - 6}{6}", True),
    ("22/7 - pi", "(22 - 7 pi)/7", True),
    ("n*2**(n-1)", "n 2^(n-1)", True),
    ("n*2**(n-1)", r"\frac{n \cdot 2^n}{2}", True),
    ("n*2**(n-1)", "2^n", False),
    ("n**2*(n+1)**2/4", r"\left(\frac{n(n+1)}{2}\right)^2", True),
    ("n/(n+1)", "1 - 1/(n+1)", True),
    ("n/(n+1)", "(n-1)/n", False),
    ("14833", "14,833", True),
    ("15", "13", False),
    ("4", "z = 4", True),
    ("329", r"\boxed{329}", True),
    ("1", "(2+sqrt(5))**(1/3) + (2-sqrt(5))**(1/3)", False),  # principal cube root of a negative is complex
    ("45", "__import__('os')", False),
    ("45", "9**9**9**9", False),
]


def _self_test() -> None:
    failures = []
    for gold, pred, expected in SELF_TESTS:
        got = answers_equivalent(pred, gold)
        if got != expected:
            failures.append((gold, pred, expected, got))
    extraction_cases = [
        ("work...\nFINAL ANSWER: 1/2", "1/2"),
        ("so the answer is \\boxed{\\frac{1}{2}}.", "\\frac{1}{2}"),
        ("FINAL ANSWER: 3\n...\nFINAL ANSWER: $\\boxed{4}$", "4"),
        ("no answer here", None),
    ]
    for text, expected in extraction_cases:
        got = extract_final_answer(text)
        if got != expected:
            failures.append(("extract", text, expected, got))
    if failures:
        for f in failures:
            print("FAIL", f)
        raise SystemExit(1)
    print(f"grader self-tests passed ({len(SELF_TESTS)} equivalence + {len(extraction_cases)} extraction cases)")


if __name__ == "__main__":
    _self_test()
