"""Generate the synthetic Jira-shaped dataset used by module 01.

Fictional program: "Northwind Digital Onboarding" at a fictional lender.
Nothing here comes from any real employer, customer or system.

Each (workstream, weekly snapshot) pair is an independent scenario built from a
named archetype. The expected RAG label is the author's design intent for that
archetype - the labels are NOT computed by the rule baseline, so the baseline can
be wrong. Two archetypes (hidden_blocker, false_alarm) are written deliberately so
that the signal lives in the comment text, which the rule baseline cannot read.
Those cases test whether a language model adds value over simple rules.

Run:  python data/synthetic/generate.py
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent
SEED = 20261104

SNAPSHOTS = [date(2026, 3, 6), date(2026, 3, 13), date(2026, 3, 20), date(2026, 3, 27)]
WORKSTREAMS = ["KYC", "Payments", "Data-Sharing", "Collections", "Reporting", "Compliance"]

# archetype -> expected RAG (the author's design intent)
EXPECTED = {
    "on_track": "GREEN",
    "false_alarm": "GREEN",
    "slipping": "AMBER",
    "silent_drift": "AMBER",
    "red_late": "RED",
    "hidden_blocker": "RED",
}

SCHEDULE = {  # workstream -> archetype for snapshots 1..4
    "KYC": ["on_track", "on_track", "slipping", "red_late"],
    "Payments": ["on_track", "on_track", "hidden_blocker", "red_late"],
    "Data-Sharing": ["on_track", "silent_drift", "silent_drift", "slipping"],
    "Collections": ["slipping", "on_track", "false_alarm", "on_track"],
    "Reporting": ["on_track", "on_track", "silent_drift", "hidden_blocker"],
    "Compliance": ["slipping", "slipping", "on_track", "on_track"],
}

PEOPLE = ["A. Lindqvist", "M. Okafor", "S. Rao", "J. Berg", "L. Moreau", "T. Haddad"]
TOPICS = {
    "KYC": ["ID document check", "liveness flow", "sanctions screening", "consent capture", "retry handling", "audit export"],
    "Payments": ["payout API", "reconciliation job", "refund flow", "webhook signing", "limits config", "settlement report"],
    "Data-Sharing": ["consent API", "bank connector", "token refresh", "data mapping", "error codes", "sandbox tests"],
    "Collections": ["reminder schedule", "dialer rules", "promise-to-pay", "agent screen", "SMS templates", "ageing report"],
    "Reporting": ["exec dashboard", "daily MIS", "data quality checks", "export to finance", "KPI definitions", "alerting"],
    "Compliance": ["policy mapping", "evidence pack", "control tests", "access review", "vendor assessment", "audit tracker"],
}
BENIGN = ["On plan.", "Reviewed in standup, no concerns.", "PR merged, testing next.", "Waiting on code review.", "Demo scheduled this week.", "Docs updated."]
DRIFT = ["Waiting for bank confirmation.", "Pending input from partner team.", "Need a decision from product, asked twice.", "Still waiting for test data."]
SLIP = ["A bit behind; recovery plan agreed with the team.", "Slipped a few days after scope clarification."]
LATE = ["Escalated to program lead.", "Behind plan; needs extra capacity.", "Overdue, dependency on another team."]
HIDDEN = "Vendor confirmed sandbox access will not be available before mid-April."


def build_issue(rng, as_of, key, workstream, idx, status, priority, due_off, upd_off, comment, blocked_by=""):
    topic = TOPICS[workstream][idx % 6]
    return {
        "Key": key,
        "Summary": f"{workstream}: {topic}",
        "Status": status,
        "Priority": priority,
        "Assignee": rng.choice(PEOPLE),
        "Workstream": workstream,
        "Story Points": rng.choice([1, 2, 3, 5, 8]),
        "Due Date": (as_of + timedelta(days=due_off)).isoformat(),
        "Updated": (as_of - timedelta(days=upd_off)).isoformat(),
        "Last Comment": comment,
        "Blocked By": blocked_by,
    }


def scenario(rng, as_of, ws_index, workstream, archetype):
    base = 100 + ws_index * 10
    keys = [f"NW-{base + i}" for i in range(8)]
    rows = []

    def add(i, status, prio, due, upd, comment, blocked=""):
        rows.append(build_issue(rng, as_of, keys[i], workstream, i, status, prio, due, upd, comment, blocked))

    # baseline healthy shape: 3 done, 3 in progress, 2 to do
    healthy = [
        (0, "Done", "Medium", -3, 4), (1, "Done", "High", -6, 5), (2, "Done", "Low", -1, 2),
        (3, "In Progress", "High", 9, 2), (4, "In Progress", "Medium", 14, 1), (5, "In Progress", "Medium", 6, 3),
        (6, "To Do", "Medium", 18, 6), (7, "To Do", "Low", 25, 7),
    ]
    for i, st, pr, due, upd in healthy:
        add(i, st, pr, due, upd, rng.choice(BENIGN))

    def override(i, **kw):
        row = rows[i]
        row.update({k: v for k, v in kw.items()})

    if archetype == "slipping":
        # a minor slip: one Medium-priority item a few days late
        override(3, Priority="Medium", **{"Due Date": (as_of - timedelta(days=3)).isoformat(), "Last Comment": rng.choice(SLIP)})
    elif archetype == "red_late":
        for i, d in [(3, -4), (4, -2), (5, -6)]:
            override(i, **{"Due Date": (as_of + timedelta(days=d)).isoformat(), "Last Comment": rng.choice(LATE)})
        override(3, Priority="Highest")
    elif archetype == "silent_drift":
        for i in (3, 4, 5):
            override(i, **{"Updated": (as_of - timedelta(days=rng.randint(9, 14))).isoformat(),
                           "Last Comment": rng.choice(DRIFT)})
    elif archetype == "hidden_blocker":
        # everything looks fresh and in-date; the comment text carries the risk
        override(3, Priority="Highest", **{"Due Date": (as_of + timedelta(days=3)).isoformat(),
                                            "Updated": as_of.isoformat(), "Last Comment": HIDDEN})
    elif archetype == "false_alarm":
        override(5, Priority="Low", **{"Due Date": (as_of - timedelta(days=4)).isoformat(),
                                        "Last Comment": f"Duplicate of {keys[4]}; cancelling, no impact on delivery."})
    return rows


def main():
    rng = random.Random(SEED)
    snap_dir = OUT / "snapshots"
    snap_dir.mkdir(exist_ok=True)
    labels = {}
    for s_idx, as_of in enumerate(SNAPSHOTS):
        rows = []
        labels[as_of.isoformat()] = {}
        for w_idx, ws in enumerate(WORKSTREAMS):
            arch = SCHEDULE[ws][s_idx]
            rows += scenario(rng, as_of, w_idx, ws, arch)
            labels[as_of.isoformat()][ws] = {"expected_rag": EXPECTED[arch], "archetype": arch}
        with (snap_dir / f"{as_of.isoformat()}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    (OUT / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"wrote {len(SNAPSHOTS)} snapshots and labels for {len(SNAPSHOTS) * len(WORKSTREAMS)} cases")


if __name__ == "__main__":
    main()
