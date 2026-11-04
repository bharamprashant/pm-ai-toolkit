import json
from datetime import date
from pathlib import Path

import pytest

from core.audit import AuditLog, approve
from core.llm import OfflineBaseline, extract_json
from modules.m01_status_agent import agent
from modules.m01_status_agent.facts import compute_facts, load_issues
from modules.m01_status_agent.eval.run_eval import evaluate

DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic"


def _facts(snap="2026-03-20", ws="Payments"):
    return compute_facts(load_issues(DATA / "snapshots" / f"{snap}.csv"), date.fromisoformat(snap))[ws]


def test_facts_are_computed_by_code():
    f = _facts("2026-03-20", "KYC")
    assert f.total == 8 and f.done == 3
    assert f.overdue == ["NW-103"]


def test_baseline_is_blind_to_comment_text():
    # Payments 2026-03-20 hides a vendor blocker in a comment; rules see nothing.
    assert agent.assess(agent.baseline(), _facts())["rag"] == "GREEN"


def test_verifier_rejects_invented_ticket_keys_and_falls_back():
    liar = OfflineBaseline(lambda s, u: {"rag": "RED", "rationale": "Sandbox issue.", "cited_keys": ["NW-999"]})
    res = agent.assess(liar, _facts())
    assert res["verified"] is False
    assert "fallback" in res["rationale"]
    assert "NW-999" not in res["cited_keys"]


def test_verifier_rejects_invalid_rag():
    bad = OfflineBaseline(lambda s, u: {"rag": "PURPLE", "rationale": "x", "cited_keys": []})
    assert agent.assess(bad, _facts())["verified"] is False


def test_a_good_model_that_reads_comments_is_accepted_and_scores_higher():
    # Stand-in for a model that notices the vendor comment. Proves the harness can show lift.
    def smart(system, user):
        facts = json.loads(user)["FACTS"]
        for key, text in facts["open_item_comments"].items():
            if "will not be available" in text:
                return {"rag": "RED", "rationale": "Vendor sandbox unavailable before due date.", "cited_keys": [key]}
        return agent._baseline_fn(system, user)

    base = evaluate(agent.baseline())
    better = evaluate(OfflineBaseline(smart))
    assert better["accuracy"] > base["accuracy"]
    assert better["grounding_rate"] == 1.0


def test_extract_json_handles_wrapped_replies():
    assert extract_json('Here you go: {"rag": "GREEN"} thanks')["rag"] == "GREEN"


def test_approval_requires_named_approver_and_logs(tmp_path):
    draft = tmp_path / "status_x_DRAFT.md"
    draft.write_text("STATUS: DRAFT - not approved\nbody\n")
    log = AuditLog(tmp_path / "audit.jsonl")
    with pytest.raises(ValueError):
        approve(draft, "  ", log)
    final = approve(draft, "Test Approver", log)
    assert "APPROVED by Test Approver" in final.read_text()
    assert "approved" in (tmp_path / "audit.jsonl").read_text()
