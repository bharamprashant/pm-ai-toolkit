"""Module 02 (meeting-to-action): date rules, checker, baseline, eval harness, approval. No network, no key."""
import json
from datetime import date
from pathlib import Path

import pytest

from core.audit import AuditLog, approve, verify_approved
from modules.m02_meeting_actions import agent
from modules.m02_meeting_actions.eval.run_eval import DATA, evaluate
from modules.m02_meeting_actions.facts import Meeting, parse_meeting, resolve_due

WED = date(2026, 3, 4)   # a Wednesday
MON = date(2026, 3, 2)


@pytest.mark.parametrize("phrase,meeting,expected", [
    ("today", WED, "2026-03-04"),
    ("tomorrow", WED, "2026-03-05"),
    ("by Friday", WED, "2026-03-06"),
    ("Wednesday", WED, "2026-03-11"),              # same weekday means next week, never today
    ("on Monday", WED, "2026-03-09"),
    ("next Tuesday", WED, "2026-03-10"),           # the following week
    ("next Friday", date(2026, 3, 18), "2026-03-27"),
    ("end of this week", MON, "2026-03-06"),
    ("end of next week", WED, "2026-03-13"),
    ("by the end of next week", WED, "2026-03-13"),
    ("by the end of this week", MON, "2026-03-06"),
    ("in 3 days", date(2026, 3, 9), "2026-03-12"),
    ("in 2 weeks", date(2026, 3, 23), "2026-04-06"),
    ("on 13 March", date(2026, 3, 9), "2026-03-13"),
    ("March 27", date(2026, 3, 23), "2026-03-27"),
    ("by 2026-03-24", date(2026, 3, 16), "2026-03-24"),
])
def test_dates_are_resolved_by_rule(phrase, meeting, expected):
    assert resolve_due(phrase, meeting).isoformat() == expected


@pytest.mark.parametrize("phrase", [None, "", "soon", "before the next sync", "when he gets a chance",
                                    "2026-02-30", "31 February", "on 1 March"])   # last is before the meeting date
def test_unresolvable_words_give_no_date(phrase):
    assert resolve_due(phrase, WED) is None


def test_parse_meeting_and_missing_header():
    m = parse_meeting("Meeting: Sync\nDate: 2026-03-02\nAttendees: A, B\n\nline one\n\nline two\n")
    assert m.title == "Sync" and m.attendees == ["A", "B"] and m.lines == ["line one", "line two"]
    with pytest.raises(ValueError):
        parse_meeting("Meeting: Sync\nDate: 2026-03-02\n\nbody")


def _meeting():
    return Meeting("Sync", MON, ["Priya", "Marcus"], ["Priya will send the contract by Friday.", "Marcus will help."])


def test_checker_rejects_invented_quote_and_outsider_owner():
    items = [
        {"owner": "Priya", "task": "x", "due_phrase": "by Friday", "quote": "Priya will send the contract by Friday."},
        {"owner": "Priya", "task": "invented", "due_phrase": None, "quote": "Priya will fly to Mars."},
        {"owner": "Zed", "task": "outsider", "due_phrase": None, "quote": "Marcus will help."},
        {"owner": "Marcus", "task": "bad words", "due_phrase": "by Tuesday", "quote": "Marcus will help."},
    ]
    ok, bad = agent.check_items(items, _meeting())
    assert [a["owner"] for a in ok] == ["Priya"] and ok[0]["due"] == "2026-03-06" and ok[0]["status"] == "OK"
    assert [b["reason"] for b in bad] == ["quote is not in the notes", "owner 'Zed' is not an attendee",
                                          "due words are not in the quote"]


def test_a_date_is_never_invented_and_gaps_are_flagged():
    items = [{"owner": None, "task": "t", "due_phrase": "will help", "quote": "Marcus will help."}]   # words present, no date in them
    ok, _ = agent.check_items(items, _meeting())
    assert ok[0]["due"] is None and ok[0]["owner"] is None and ok[0]["status"] == "NEEDS OWNER+DATE"
    soon = [{"owner": "Marcus", "task": "t", "due_phrase": "soon", "quote": "Marcus will help."}]
    assert agent.check_items(soon, _meeting())[1][0]["reason"] == "due words are not in the quote"


def test_duplicates_and_junk_items_are_dropped():
    q = "Marcus will help."
    ok, bad = agent.check_items([{"owner": "Marcus", "quote": q}, {"owner": "Marcus", "quote": q}, "junk"], _meeting())
    assert len(ok) == 1 and bad[0]["reason"] == "duplicate of an earlier action"


def test_unusable_model_answer_falls_back_to_rules_and_is_flagged():
    class Bad:
        name = "bad"

        def complete_json(self, s, u):
            return {"oops": 1}
    m = parse_meeting((DATA / "meetings" / "2026-03-02.txt").read_text())
    res = agent.assess(Bad(), m)
    assert res["fallback"] and len(res["actions"]) == 1
    assert "fallback" in agent.render(m, res, "bad")


def test_baseline_numbers_on_the_synthetic_set():
    r = evaluate(agent.baseline())
    assert (r["labelled_actions"], r["reported"]) == (29, 9)
    assert round(r["recall"], 3) == round(9 / 29, 3) and r["precision"] == 1.0
    assert r["recall_by_archetype"] == {"explicit": 1.0, "implicit": 0.0, "no_date": 0.0, "no_owner": 0.0}
    assert r["grounding"] == 1.0 and round(r["due_correct"], 3) == round(8 / 9, 3)


class _GoodModel:
    """Simulated perfect model: proves the harness can show an improvement. Not a result about any real model."""
    name = "simulated-good-model"

    def complete_json(self, system, user):
        data = json.loads(user)
        meeting_date = date.fromisoformat(data["MEETING_DATE"])
        labels = json.loads((DATA / "meeting_labels.json").read_text())
        out = []
        for lab in next(v for k, v in labels.items() if k == meeting_date.isoformat()):
            words = lab["quote"].rstrip(".").split()
            phrase = None
            if lab["due"]:
                phrase = next(" ".join(words[i:]) for i in range(len(words))
                              if (resolve_due(" ".join(words[i:]), meeting_date) or None) and
                              resolve_due(" ".join(words[i:]), meeting_date).isoformat() == lab["due"])
            out.append({"owner": lab["owner"], "task": lab["quote"], "due_phrase": phrase, "quote": lab["quote"]})
        return {"actions": out}


def test_a_good_model_scores_higher_so_the_harness_can_show_improvement():
    base, good = evaluate(agent.baseline()), evaluate(_GoodModel())
    assert good["recall"] == 1.0 and good["all_correct"] == 1.0 and good["precision"] == 1.0
    assert good["all_correct"] > base["all_correct"]


def test_draft_then_named_approval_then_verified(tmp_path):
    m = parse_meeting((DATA / "meetings" / "2026-03-02.txt").read_text())
    draft = tmp_path / "actions_2026-03-02_DRAFT.md"
    draft.write_text(agent.render(m, agent.assess(agent.baseline(), m), "offline-baseline"), encoding="utf-8")
    assert "STATUS: DRAFT - not approved" in draft.read_text()
    log = AuditLog(tmp_path / "audit.jsonl")
    with pytest.raises(ValueError):
        approve(draft, "  ", log)
    final = approve(draft, "Pat Approver", log)
    assert "APPROVED by Pat Approver" in final.read_text()
    assert verify_approved(final, tmp_path / "audit.jsonl")
    final.write_text(final.read_text() + "edited", encoding="utf-8")
    with pytest.raises(ValueError):
        verify_approved(final, tmp_path / "audit.jsonl")


def test_labels_are_consistent_with_the_notes():
    labels = json.loads((DATA / "meeting_labels.json").read_text())
    for mid, items in labels.items():
        text = (DATA / "meetings" / f"{mid}.txt").read_text()
        for it in items:
            assert it["quote"] in text


def test_heldout_labels_agree_with_the_date_rules_and_checker():
    """An oracle that returns the hand labels must score 100%: proves the held-out labels are consistent with the
    published date rules (a wrong hand-worked date would fail here), not that any model is good."""
    class Oracle:
        name = "oracle"
        def __init__(self): self.labels = json.loads((DATA / "heldout" / "labels.json").read_text())
        def complete_json(self, system, user):
            mid = next(m for m in self.labels if f'"MEETING_DATE": "{m}"' in user)
            return {"actions": [{"owner": a["owner"], "task": a["quote"], "quote": a["quote"],
                               "due_phrase": _phrase(a["quote"], a["due"])} for a in self.labels[mid]]}
    def _phrase(quote, due):
        if due is None:
            return None
        import re
        m = re.search(r"(by the end of next week|end of next week|end of this week|next Monday|in 3 days|tomorrow|"
                      r"on Friday|due Friday|Friday|Wednesday|15 June|30 June|2026-06-24)", quote)
        return m.group(1)
    r = evaluate(Oracle(), "heldout")
    assert r["labelled_actions"] == 18 and r["recall"] == 1.0 and r["all_correct"] == 1.0, r["wrong_fields"]


def test_heldout_baseline_runs():
    r = evaluate(agent.baseline(), "heldout")
    assert r["labelled_actions"] == 18 and 0 <= r["recall"] < 1
