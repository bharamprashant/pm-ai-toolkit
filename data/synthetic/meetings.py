"""Synthetic meeting notes with hand-written answers, for module 02 (meeting-to-action).

  python data/synthetic/meetings.py     # writes data/synthetic/meetings/*.txt and meeting_labels.json

Everything is fictional. The labels (who owns each action and its due date) were written by hand,
independently of the code that resolves dates, so the evaluation is not grading the code against itself.
Meeting dates: Mondays and Wednesdays in March 2026 (2 Mar 2026 is a Monday).
Archetypes: explicit (an "Action:" line with owner and date), implicit (the same commitment in ordinary
prose), no_date (a named owner but no date the code can resolve), no_owner (nobody named).
"""
from __future__ import annotations

import json
from pathlib import Path

TEAM = ["Priya", "Marcus", "Sofia", "Lee", "Dana", "Omar"]


def A(line, owner, due, kind):
    return {"quote": line, "owner": owner, "due": due, "archetype": kind}


MEETINGS = [
    {"id": "2026-03-02", "title": "Weekly programme sync", "date": "2026-03-02", "attendees": TEAM[:5],
     "lines": [
         "Action: Priya to send the KYC vendor contract by Friday.",
         "Marcus said he will chase the bank for the sandbox credentials by Wednesday.",
         "We decided to use SFTP for the payroll file exchange.",
         "Someone needs to update the risk log.",
         "Sofia will draft the communications plan.",
         "Priya already sent the invoice to finance last week.",
     ],
     "actions": [
         ("Action: Priya to send the KYC vendor contract by Friday.", "Priya", "2026-03-06", "explicit"),
         ("Marcus said he will chase the bank for the sandbox credentials by Wednesday.", "Marcus", "2026-03-04", "implicit"),
         ("Someone needs to update the risk log.", None, None, "no_owner"),
         ("Sofia will draft the communications plan.", "Sofia", None, "no_date"),
     ]},
    {"id": "2026-03-04", "title": "Integration checkpoint", "date": "2026-03-04", "attendees": TEAM,
     "lines": [
         "ACTION: Lee to book the steering committee room for next Tuesday.",
         "Dana will confirm the penetration test slot by end of next week.",
         "Omar to review the data processing agreement by tomorrow.",
         "Budget approval is still pending from finance.",
         "Marcus to follow up on the escalation.",
     ],
     "actions": [
         ("ACTION: Lee to book the steering committee room for next Tuesday.", "Lee", "2026-03-10", "explicit"),
         ("Dana will confirm the penetration test slot by end of next week.", "Dana", "2026-03-13", "implicit"),
         ("Omar to review the data processing agreement by tomorrow.", "Omar", "2026-03-05", "implicit"),
         ("Marcus to follow up on the escalation.", "Marcus", None, "no_date"),
     ]},
    {"id": "2026-03-09", "title": "Weekly programme sync", "date": "2026-03-09", "attendees": TEAM,
     "lines": [
         "Action: Sofia to share the revised plan on 13 March.",
         "Dana mentioned she'd look into the reconciliation mismatch before the next sync.",
         "We agreed the go-live stays on 30 April.",
         "Lee will prepare the test data in 3 days.",
         "Could we also revisit the vendor shortlist at some point?",
     ],
     "actions": [
         ("Action: Sofia to share the revised plan on 13 March.", "Sofia", "2026-03-13", "explicit"),
         ("Dana mentioned she'd look into the reconciliation mismatch before the next sync.", "Dana", None, "no_date"),
         ("Lee will prepare the test data in 3 days.", "Lee", "2026-03-12", "implicit"),
     ]},
    {"id": "2026-03-11", "title": "Vendor escalation call", "date": "2026-03-11", "attendees": TEAM,
     "lines": [
         "ACTION: Priya to escalate the vendor delay to the sponsor today.",
         "Marcus will pair with Omar on the SSO fix by Friday.",
         "Dana is going to send the weekly report on Monday.",
         "The sandbox is down again, which is annoying.",
     ],
     "actions": [
         ("ACTION: Priya to escalate the vendor delay to the sponsor today.", "Priya", "2026-03-11", "explicit"),
         ("Marcus will pair with Omar on the SSO fix by Friday.", "Marcus", "2026-03-13", "implicit"),
         ("Dana is going to send the weekly report on Monday.", "Dana", "2026-03-16", "implicit"),
     ]},
    {"id": "2026-03-16", "title": "Weekly programme sync", "date": "2026-03-16", "attendees": TEAM,
     "lines": [
         "Action: Lee to fix the file-naming bug by end of this week.",
         "Omar said he will check with legal about the retention clause by 2026-03-24.",
         "Priya is waiting on the bank for the certificate.",
         "Somebody should tell the vendor about the new date.",
         "Dana will send the minutes tomorrow.",
     ],
     "actions": [
         ("Action: Lee to fix the file-naming bug by end of this week.", "Lee", "2026-03-20", "explicit"),
         ("Omar said he will check with legal about the retention clause by 2026-03-24.", "Omar", "2026-03-24", "implicit"),
         ("Somebody should tell the vendor about the new date.", None, None, "no_owner"),
         ("Dana will send the minutes tomorrow.", "Dana", "2026-03-17", "implicit"),
     ]},
    {"id": "2026-03-18", "title": "Release readiness", "date": "2026-03-18", "attendees": TEAM,
     "lines": [
         "ACTION: Marcus to rotate the SFTP keys next Friday.",
         "Sofia will update the RAID log by Thursday.",
         "Lee volunteered to demo the dashboard.",
         "We decided to drop the second pilot bank.",
         "Omar already closed the access ticket yesterday.",
     ],
     "actions": [
         ("ACTION: Marcus to rotate the SFTP keys next Friday.", "Marcus", "2026-03-27", "explicit"),
         ("Sofia will update the RAID log by Thursday.", "Sofia", "2026-03-19", "implicit"),
         ("Lee volunteered to demo the dashboard.", "Lee", None, "no_date"),
     ]},
    {"id": "2026-03-23", "title": "Weekly programme sync", "date": "2026-03-23", "attendees": TEAM,
     "lines": [
         "Action: Dana to book the UAT window by Wednesday.",
         "Priya will confirm the contract signature in 2 weeks.",
         "Everyone needs to read the security policy.",
         "Action: Omar to send the data-sharing agreement on 27 March.",
     ],
     "actions": [
         ("Action: Dana to book the UAT window by Wednesday.", "Dana", "2026-03-25", "explicit"),
         ("Priya will confirm the contract signature in 2 weeks.", "Priya", "2026-04-06", "implicit"),
         ("Everyone needs to read the security policy.", None, None, "no_owner"),
         ("Action: Omar to send the data-sharing agreement on 27 March.", "Omar", "2026-03-27", "explicit"),
     ]},
    {"id": "2026-03-25", "title": "Go-live planning", "date": "2026-03-25", "attendees": TEAM,
     "lines": [
         "ACTION: Sofia to publish the release notes by end of next week.",
         "Lee said he'd have a look at the failing build when he gets a chance.",
         "Dana will circulate the updated plan by Friday.",
         "The vendor's invoice was paid last week.",
         "Marcus to check certificate expiry.",
     ],
     "actions": [
         ("ACTION: Sofia to publish the release notes by end of next week.", "Sofia", "2026-04-03", "explicit"),
         ("Lee said he'd have a look at the failing build when he gets a chance.", "Lee", None, "no_date"),
         ("Dana will circulate the updated plan by Friday.", "Dana", "2026-03-27", "implicit"),
         ("Marcus to check certificate expiry.", "Marcus", None, "no_date"),
     ]},
]


def render(m: dict) -> str:
    return (f"Meeting: {m['title']}\nDate: {m['date']}\nAttendees: {', '.join(m['attendees'])}\n\n"
            + "\n".join(m["lines"]) + "\n")


def main() -> None:
    root = Path(__file__).resolve().parent
    out = root / "meetings"
    out.mkdir(exist_ok=True)
    labels = {}
    for m in MEETINGS:
        (out / f"{m['id']}.txt").write_text(render(m), encoding="utf-8")
        for quote, *_ in m["actions"]:
            assert quote in m["lines"], quote
        labels[m["id"]] = [{"quote": q, "owner": o, "due": d, "archetype": k} for q, o, d, k in m["actions"]]
    (root / "meeting_labels.json").write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    n = sum(len(v) for v in labels.values())
    print(f"wrote {len(MEETINGS)} meetings and labels for {n} actions")


if __name__ == "__main__":
    main()
