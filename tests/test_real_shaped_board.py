"""Regression tests from the first run on a real Jira board (AGPMO, 11 Nov 2026):
no due dates, dependency links to finished work, unowned stories."""
from datetime import date

from modules.m01_status_agent.agent import assess, baseline, render
from modules.m01_status_agent.facts import Issue, compute_facts
from modules.m01_status_agent.jira_client import to_rows

AS_OF = date(2026, 11, 11)
NO_DATE = date(2099, 12, 31)


def issue(key, status="To Do", assignee="Ana", due=NO_DATE, blocked_by="", ws="W"):
    return Issue(key, key, status, "Medium", assignee, ws, 1, due, date(2026, 11, 10), "", blocked_by)


def test_link_to_a_done_blocker_is_not_blocked():
    f = compute_facts([issue("A-1", status="Done"), issue("A-2", blocked_by="A-1")], AS_OF)["W"]
    assert f.blocked == []


def test_link_to_an_open_or_unknown_blocker_is_blocked():
    f = compute_facts([issue("A-1"), issue("A-2", blocked_by="A-1"), issue("A-3", blocked_by="X-9")], AS_OF)["W"]
    assert f.blocked == ["A-2", "A-3"]


def test_no_due_dates_is_never_a_clean_green():
    facts = compute_facts([issue("A-1")], AS_OF)
    res = assess(baseline(), facts["W"])
    assert facts["W"].no_schedule and res["rag"] == "AMBER" and "due dates" in res["rationale"]


def test_a_dated_workstream_can_still_be_green():
    facts = compute_facts([issue("A-1", due=date(2026, 12, 1))], AS_OF)
    assert assess(baseline(), facts["W"])["rag"] == "GREEN"


def test_unowned_open_stories_become_a_decision():
    facts = compute_facts([issue("A-1", assignee="Unassigned", due=date(2026, 12, 1)),
                           issue("A-2", status="Done", assignee="Unassigned")], AS_OF)
    res = {w: assess(baseline(), f) for w, f in facts.items()}
    out = render(AS_OF, "T", res, facts, "offline")
    assert res["W"]["rag"] == "AMBER" and "assign an owner to A-1." in out and "A-2" not in out.split("Decisions")[1]


def test_all_blocking_links_are_kept_by_the_jira_mapping():
    def link(k): return {"type": {"inward": "is blocked by"}, "inwardIssue": {"key": k}}
    it = {"key": "A-9", "fields": {"summary": "s", "status": {"name": "To Do"}, "updated": "2026-11-01T00:00:00",
                                   "issuelinks": [link("A-1"), link("A-2")]}}
    assert to_rows([it])[0]["Blocked By"] == "A-1,A-2"


def test_zero_issues_gives_a_clear_message_not_a_traceback(monkeypatch, tmp_path):
    import pytest
    from modules.m01_status_agent import jira_client
    monkeypatch.setattr(jira_client, "fetch", lambda jql, limit=200: [])
    with pytest.raises(SystemExit, match="0 issues"):
        jira_client.export_csv("project = X", tmp_path / "o.csv")
