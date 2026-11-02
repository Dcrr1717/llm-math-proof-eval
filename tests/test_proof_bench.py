"""Offline tests for proof_bench.py (no API calls)."""
import proof_bench as pb


def test_parse_judgment_takes_last_valid_block():
    text = (
        "analysis...\n```json\n{\"verdict\": \"maybe\"}\n```\n"
        "revised:\n```json\n{\"checkpoints\": [], \"fatal_issue\": null, "
        "\"verdict\": \"minor_gaps\", \"score\": 7}\n```"
    )
    j = pb.parse_judgment(text)
    assert j["verdict"] == "minor_gaps" and j["score"] == 7


def test_parse_judgment_rejects_missing_or_bad_json():
    assert pb.parse_judgment("no block here") is None
    assert pb.parse_judgment("```json\n{not json}\n```") is None


def test_judge_text_hides_author_and_lists_steps():
    item = {"definitions": "Let X be a space.", "statement": "X is fine.",
            "checkpoints": ["step a", "step b"], "pitfalls": "p"}
    t = pb.judge_text(item, "Proof. Trivial.")
    assert "1. step a" in t and "2. step b" in t
    assert "author withheld" in t and "claude" not in t.lower()


def test_report_aggregates(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "ITEMS", tmp_path / "items.jsonl")
    monkeypatch.setattr(pb, "SOLUTIONS", tmp_path / "solutions.jsonl")
    monkeypatch.setattr(pb, "JUDGMENTS", tmp_path / "judgments.jsonl")
    monkeypatch.setattr(pb, "REPORT", tmp_path / "report.md")
    pb.append_jsonl(pb.ITEMS, {"id": "a", "source": {"arxiv_v1": "2026-03-01"},
                               "statement": "s", "checkpoints": []})
    pb.append_jsonl(pb.SOLUTIONS, {"id": "a", "model": "m", "sample": 0,
                                   "status": "ok", "cost_usd": 0.5, "text": "p"})
    for r, v in enumerate(["correct", "minor_gaps"]):
        pb.append_jsonl(pb.JUDGMENTS, {"id": "a", "model": "m", "sample": 0,
                                       "judge": "j", "repeat": r, "verdict": v})
    pb.append_jsonl(pb.SOLUTIONS, {"id": "a", "model": "m", "sample": 1,
                                   "status": "truncated", "cost_usd": 0.5})
    out = pb.report()
    # the truncated answer counts as a proof scoring 0
    assert "| m | 2 | 0.44 | 0/2 | 1 | $1.00 | $0.500 |" in out
    assert "identical verdict on 0/1" in out
    assert "| m | - | 0.44 (n=2) |" in out
