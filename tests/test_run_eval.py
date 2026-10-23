import asyncio
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import run_eval

ROOT = Path(__file__).resolve().parents[1]


def test_cost_from_usage():
    # claude-opus-5-5: $4 / $20 per million tokens.
    assert run_eval.cost_usd("claude-opus-5-5", 1_000_000, 0) == pytest.approx(4.0)
    assert run_eval.cost_usd("claude-opus-5-5", 200, 5_000) == pytest.approx((200 * 4 + 5_000 * 20) / 1e6)
    assert run_eval.cost_usd("not-a-model", 1, 1) is None


def test_haiku_long_prompt_tier():
    short = run_eval.cost_usd("claude-haiku-5-5", 100_000, 1_000)
    long = run_eval.cost_usd("claude-haiku-5-5", 100_001, 1_000)
    assert short == pytest.approx((100_000 * 0.10 + 1_000 * 0.50) / 1e6)
    assert long == pytest.approx((100_001 * 0.50 + 1_000 * 2.50) / 1e6)


def test_report_from_sample_results(tmp_path):
    report = tmp_path / "report.md"
    assert run_eval.main(["--from-results", str(ROOT / "sample_results.jsonl"), "--report", str(report)]) == 0
    text = report.read_text()
    assert "SYNTHETIC DEMO DATA" in text
    for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
        assert f"`{model}`" in text
    assert "Cost / correct" in text and "Accuracy by topic" in text


def test_sample_results_are_regraded_not_trusted():
    rows = [run_eval.grade_record(r) for r in run_eval.load_results(ROOT / "sample_results.jsonl")]
    assert all(r["synthetic"] for r in rows)
    summary = run_eval.summarize(rows)
    assert summary["claude-opus-5-5"]["correct"] == 19
    assert summary["claude-haiku-5-5"]["errors"] == 1


def test_limit_with_from_results(tmp_path):
    report = tmp_path / "r.md"
    run_eval.main(["--from-results", str(ROOT / "sample_results.jsonl"), "--limit", "3", "--report", str(report)])
    assert "| `claude-opus-5-5` | 100% | 3/3 |" in report.read_text()


def test_no_api_key_exits_cleanly():
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    proc = subprocess.run(
        [sys.executable, "run_eval.py", "--limit", "1"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0
    assert "ANTHROPIC_API_KEY is not set" in proc.stdout


class _FakeStream:
    def __init__(self, message):
        self._message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        return self._message


class _FakeClient:
    """Stands in for AsyncAnthropic; records request kwargs, never touches the network."""

    def __init__(self, text, stop_reason="end_turn", served_model=None):
        self.calls = []
        self._text, self._stop, self._served = text, stop_reason, served_model
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(
            model=self._served or kwargs["model"],
            stop_reason=self._stop,
            usage=SimpleNamespace(input_tokens=180, output_tokens=4_000),
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self._text)],
        )
        return _FakeStream(msg)


PROBLEM = {"id": "CALC-01", "topic": "calculus", "difficulty": "medium", "format": "answer",
           "statement": "...", "answer": "1/2"}


def _solve(client, model="claude-opus-5-5"):
    return asyncio.run(run_eval.solve_one(client, PROBLEM, model, "high", 64_000, asyncio.Semaphore(1)))


def test_solve_one_request_shape_and_grading():
    client = _FakeClient("Integrate by parts...\nFINAL ANSWER: \\frac{1}{2}")
    r = _solve(client)
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "high"}
    assert call["fallbacks"] == "default" and call["betas"] == [run_eval.FALLBACK_BETA]
    assert r["correct"] and r["status"] == "ok"
    assert r["cost_usd"] == pytest.approx((180 * 4 + 4_000 * 20) / 1e6)


def test_no_fallbacks_for_models_without_support():
    client = _FakeClient("FINAL ANSWER: 1/2")
    _solve(client, model="claude-haiku-5-5")
    assert "fallbacks" not in client.calls[0] and "betas" not in client.calls[0]


def test_refusal_and_truncation_are_marked_and_graded_wrong():
    r = _solve(_FakeClient("", stop_reason="refusal"))
    assert r["status"] == "refusal" and not r["correct"]
    r = _solve(_FakeClient("long reasoning without an answer", stop_reason="max_tokens"))
    assert r["status"] == "truncated" and r["grade_method"] == "no_answer"


def test_cost_uses_served_model_after_fallback():
    r = _solve(_FakeClient("FINAL ANSWER: 0.5", served_model="claude-opus-4-8"))
    assert r["served_model"] == "claude-opus-4-8"
    assert r["cost_usd"] == pytest.approx((180 * 5 + 4_000 * 25) / 1e6)
