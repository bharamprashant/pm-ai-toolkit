"""Deterministic facts engine.

The model never counts, dates or sums. This code computes the facts; the model
only judges and explains them. That separation is the main hallucination guard.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Thresholds are published in the README; change them here and re-run the eval.
STALE_DAYS = 7
RED_OVERDUE_SHARE = 0.25
STALE_AMBER_COUNT = 2
CRITICAL = {"Highest", "High"}
NO_DUE_YEAR = 2099  # jira_client writes 2099-12-31 when an issue has no due date: "no date", not "far future"
UNASSIGNED = {"", "Unassigned"}


@dataclass
class Issue:
    key: str
    summary: str
    status: str
    priority: str
    assignee: str
    workstream: str
    points: int
    due: date
    updated: date
    comment: str
    blocked_by: str


@dataclass
class WorkstreamFacts:
    workstream: str
    as_of: date
    total: int
    done: int
    points_done: int
    points_total: int
    overdue: list[str] = field(default_factory=list)
    overdue_critical: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    unowned: list[str] = field(default_factory=list)   # open items with no assignee
    open_dated: int = 0                                  # open items that carry a real due date
    comments: dict[str, str] = field(default_factory=dict)  # key -> last comment (open items only)

    @property
    def no_schedule(self) -> bool:
        """Open work exists but none of it has a due date, so 'overdue' can never fire."""
        return (self.total - self.done) > 0 and self.open_dated == 0

    @property
    def overdue_share(self) -> float:
        open_items = self.total - self.done
        return len(self.overdue) / open_items if open_items else 0.0

    def to_dict(self) -> dict:
        return {
            "workstream": self.workstream, "as_of": self.as_of.isoformat(),
            "total_issues": self.total, "done": self.done,
            "points_done": self.points_done, "points_total": self.points_total,
            "overdue": self.overdue, "overdue_critical": self.overdue_critical,
            "blocked": self.blocked, "stale_over_%dd" % STALE_DAYS: self.stale,
            "overdue_share_of_open": round(self.overdue_share, 2),
            "unassigned_open": self.unowned,
            "no_schedule_data": self.no_schedule,
            "open_item_comments": self.comments,
        }


def load_issues(path: str | Path) -> list[Issue]:
    issues = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            issues.append(Issue(
                key=r["Key"], summary=r["Summary"], status=r["Status"], priority=r["Priority"],
                assignee=r["Assignee"], workstream=r["Workstream"], points=int(r["Story Points"] or 0),
                due=date.fromisoformat(r["Due Date"]), updated=date.fromisoformat(r["Updated"]),
                comment=r["Last Comment"], blocked_by=r["Blocked By"],
            ))
    return issues


def compute_facts(issues: list[Issue], as_of: date) -> dict[str, WorkstreamFacts]:
    by_ws: dict[str, WorkstreamFacts] = {}
    status = {i.key: i.status for i in issues}
    for i in issues:
        f = by_ws.setdefault(i.workstream, WorkstreamFacts(i.workstream, as_of, 0, 0, 0, 0))
        f.total += 1
        f.points_total += i.points
        if i.status == "Done":
            f.done += 1
            f.points_done += i.points
            continue
        f.comments[i.key] = i.comment
        if i.assignee in UNASSIGNED:
            f.unowned.append(i.key)
        if i.due.year < NO_DUE_YEAR:
            f.open_dated += 1
        if i.due < as_of:
            f.overdue.append(i.key)
            if i.priority in CRITICAL:
                f.overdue_critical.append(i.key)
        # A link to a blocker only counts while that blocker is not Done. A key we cannot see stays blocking.
        live_blockers = [k for k in i.blocked_by.replace(";", ",").split(",")
                         if k.strip() and status.get(k.strip()) != "Done"]
        if i.status == "Blocked" or live_blockers:
            f.blocked.append(i.key)
        if i.status == "In Progress" and (as_of - i.updated).days > STALE_DAYS:
            f.stale.append(i.key)
    return by_ws


def rule_rag(f: WorkstreamFacts) -> tuple[str, str]:
    """The rule baseline: simple, explainable, blind to comment text."""
    if f.overdue_share >= RED_OVERDUE_SHARE or f.overdue_critical:
        return "RED", "overdue share or a critical item is past due"
    if f.overdue or f.blocked or len(f.stale) >= STALE_AMBER_COUNT:
        return "AMBER", "some overdue, blocked or stale items"
    if f.no_schedule:
        return "AMBER", "no schedule data: open items have no due dates, so on-time cannot be judged"
    if f.unowned:
        return "AMBER", "open items have no owner"
    return "GREEN", "no overdue, blocked or stale items"
