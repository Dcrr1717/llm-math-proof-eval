import pytest

from grader import (
    SELF_TESTS,
    answers_equivalent,
    extract_final_answer,
    grade,
    parse_answer,
)


@pytest.mark.parametrize("gold,pred,expected", SELF_TESTS)
def test_self_tests(gold, pred, expected):
    assert answers_equivalent(pred, gold) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("reasoning\nFINAL ANSWER: 42", "42"),
        ("Final answer: 7/3.", "7/3."),
        ("we get \\boxed{\\frac{\\pi^{2}}{6}} as claimed", "\\frac{\\pi^{2}}{6}"),
        ("FINAL ANSWER: 1\nwait, recheck\nFINAL ANSWER: 2", "2"),
        ("", None),
        ("no marker at all", None),
    ],
)
def test_extraction(text, expected):
    assert extract_final_answer(text) == expected


def test_grade_methods():
    assert grade("FINAL ANSWER: 1/2", "1/2").method == "exact"
    assert grade("FINAL ANSWER: n 2^(n-1)", "n*2**(n-1)").correct
    assert grade("nothing", "1").method == "no_answer"
    assert grade("FINAL ANSWER: ???", "1").method == "unparseable"


def test_numeric_fallback_for_constants_sympy_cannot_simplify():
    # Same constant written two ways; tolerance is 1e-25 at 50 digits.
    r = grade("FINAL ANSWER: log(2**(-pi/2))", "-pi*log(2)/2")
    assert r.correct


def test_decimal_approximation_of_irrational_is_rejected():
    assert not answers_equivalent("-1.08879304515180", "-pi*log(2)/2")
    assert not answers_equivalent("0.00126448926734968", "22/7 - pi")


def test_symbolic_answers_with_free_variable():
    assert answers_equivalent("(n^2 + n)^2/4", "n**2*(n+1)**2/4")
    assert not answers_equivalent("n^2 (n+1)^2 / 2", "n**2*(n+1)**2/4")
    # Extra free variable that the gold answer does not have is wrong.
    assert not answers_equivalent("n*x", "n")


@pytest.mark.parametrize(
    "malicious",
    [
        "__import__('os').system('echo hi')",
        "open('x')",
        "lambda: 1",
        "1; 2",
        "a" * 500,
        "9**9**9**9",
        "2^(10^9)",
    ],
)
def test_unsafe_or_huge_inputs_are_rejected(malicious):
    assert parse_answer(malicious) is None


def test_gold_must_parse():
    with pytest.raises(ValueError):
        grade("FINAL ANSWER: 1", "import os")
