"""Second, harder meeting set for module 02, written AFTER the module 02 prompt (agent.SYSTEM) was frozen.

  python data/synthetic/heldout.py    # writes data/synthetic/heldout/meetings/*.txt and labels.json

What "held out" means here, and what it does not: the prompt was not edited after these notes were written,
and none of these notes was used to tune anything. It does NOT mean independent: the same author (Claude)
wrote the first set, the prompt and this set. Different people writing the notes would be a stronger test.
Styles added on purpose: speaker-prefixed lines ("Raj: I'll ..."), bullet lists, passive voice, "to" without
"Action:", hedges, past-tense and future-fact lines that look like actions but are not, and dates the code cannot
resolve ("after the call with legal"). The date labels were worked out by hand from the published date rules.
Meeting dates: June 2026 (3 Jun is a Wednesday).
"""
from __future__ import annotations

import json
from pathlib import Path

TEAM = ["Anna", "Raj", "Mei", "Tomas", "Elin", "Ben"]

MEETINGS = [
    {"id": "2026-06-03", "title": "Release readiness", "date": "2026-06-03", "attendees": TEAM,
     "lines": [
         "Raj: I'll get the load test results to Mei by Friday.",
         "Anna: We agreed not to ship the export feature this sprint.",
         "Someone should check the staging certificate before release.",
         "Tomas: Last week I fixed the login timeout.",
         "Elin will write the release notes by the end of next week.",
     ],
     "actions": [
         ("Raj: I'll get the load test results to Mei by Friday.", "Raj", "2026-06-05", "implicit"),
         ("Someone should check the staging certificate before release.", None, None, "no_owner"),
         ("Elin will write the release notes by the end of next week.", "Elin", "2026-06-12", "implicit"),
     ]},
    {"id": "2026-06-08", "title": "Vendor and audit follow-ups", "date": "2026-06-08", "attendees": TEAM,
     "lines": [
         "The vendor list needs to be sent to procurement by 15 June.",
         "Tomas has promised to call the auditor in 3 days.",
         "Anna already booked the workshop room.",
         "Nobody is going to chase the old ticket; we closed it.",
         "Elin to follow up with legal next Monday.",
     ],
     "actions": [
         ("The vendor list needs to be sent to procurement by 15 June.", None, "2026-06-15", "no_owner"),
         ("Tomas has promised to call the auditor in 3 days.", "Tomas", "2026-06-11", "implicit"),
         ("Elin to follow up with legal next Monday.", "Elin", "2026-06-15", "implicit"),
     ]},
    {"id": "2026-06-10", "title": "Dashboard and compliance", "date": "2026-06-10", "attendees": TEAM,
     "lines": [
         "Mei said she would try to have the dashboard ready tomorrow.",
         "Anna will send the agenda on Friday.",
         "Tomas will finish the migration.",
         "Ben will be on leave from Monday.",
         "Everyone must complete the compliance training by 30 June.",
     ],
     "actions": [
         ("Mei said she would try to have the dashboard ready tomorrow.", "Mei", "2026-06-11", "implicit"),
         ("Anna will send the agenda on Friday.", "Anna", "2026-06-12", "implicit"),
         ("Tomas will finish the migration.", "Tomas", None, "no_date"),
         ("Everyone must complete the compliance training by 30 June.", None, "2026-06-30", "no_owner"),
     ]},
    {"id": "2026-06-17", "title": "DR test planning", "date": "2026-06-17", "attendees": TEAM,
     "lines": [
         "Action items:",
         "- Ben: draft the DR test plan (due 2026-06-24)",
         "- Mei: confirm the vendor SLA (due Friday)",
         "- TBD: pick a date for the audit workshop",
         "Decision: we will use the existing monitoring stack.",
     ],
     "actions": [
         ("- Ben: draft the DR test plan (due 2026-06-24)", "Ben", "2026-06-24", "explicit"),
         ("- Mei: confirm the vendor SLA (due Friday)", "Mei", "2026-06-19", "explicit"),
         ("- TBD: pick a date for the audit workshop", None, None, "no_owner"),
     ]},
    {"id": "2026-06-22", "title": "Pricing and results", "date": "2026-06-22", "attendees": TEAM,
     "lines": [
         "Raj will get back to us on pricing after the call with legal.",
         "Elin finished the audit checklist on Friday.",
         "Anna will present the results on Wednesday.",
         "Tomas is going to circulate the minutes tomorrow.",
         "Mei needs to renew the vendor licence by end of this week.",
     ],
     "actions": [
         ("Raj will get back to us on pricing after the call with legal.", "Raj", None, "no_date"),
         ("Anna will present the results on Wednesday.", "Anna", "2026-06-24", "implicit"),
         ("Tomas is going to circulate the minutes tomorrow.", "Tomas", "2026-06-23", "implicit"),
         ("Mei needs to renew the vendor licence by end of this week.", "Mei", "2026-06-26", "implicit"),
     ]},
    {"id": "2026-06-24", "title": "Mostly status", "date": "2026-06-24", "attendees": TEAM,
     "lines": [
         "Anna reported that the sandbox migration is complete.",
         "We decided to postpone the pilot to July.",
         "Ben mentioned he will be at a conference next week.",
         "Elin will send the final invoice by Friday.",
     ],
     "actions": [
         ("Elin will send the final invoice by Friday.", "Elin", "2026-06-26", "implicit"),
     ]},
]


def render(m: dict) -> str:
    return (f"Meeting: {m['title']}\nDate: {m['date']}\nAttendees: {', '.join(m['attendees'])}\n\n"
            + "\n".join(m["lines"]) + "\n")


def main() -> None:
    root = Path(__file__).resolve().parent / "heldout"
    (root / "meetings").mkdir(parents=True, exist_ok=True)
    labels = {}
    for m in MEETINGS:
        (root / "meetings" / f"{m['id']}.txt").write_text(render(m), encoding="utf-8")
        for quote, *_ in m["actions"]:
            assert quote in m["lines"], quote
        labels[m["id"]] = [{"quote": q, "owner": o, "due": d, "archetype": k} for q, o, d, k in m["actions"]]
    (root / "labels.json").write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(MEETINGS)} meetings and labels for {sum(len(v) for v in labels.values())} actions")


if __name__ == "__main__":
    main()
