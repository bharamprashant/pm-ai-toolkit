# Module 02 - Meeting-to-action pipeline

**Problem.** Every meeting ends with commitments buried in the notes: "Marcus said he will chase the bank by Wednesday".
Turning them into an owner, a task and a due date is slow, and the two shortcuts both fail. A template ("Action: ...")
only catches the people who follow it, and a model left alone can invent an owner, quote a sentence nobody wrote, or
turn "by Friday" into the wrong date.

**Design.** The model finds and words the actions. Code does everything that can be checked.

```
meeting notes --> parse (title, date, attendees) --> model or rules propose actions {owner, task, due words, quote}
   --> checker: quote must be in the notes word for word; owner must be an attendee; due words must be in the quote
   --> CODE turns the due words into a calendar date, or leaves it empty (never guessed)
   --> DRAFT: Actions | Needs clarification | Rejected --> named human --approve--> FINAL     (every step --> audit.jsonl)
```

| Principle | What it means here |
|---|---|
| **Code resolves dates** | The model copies "by Friday"; `facts.py` turns it into a date with fixed, tested rules. A model never writes a date |
| **Every action quotes the notes** | An item whose quote is not in the notes is rejected, so a made-up action cannot reach the draft |
| **Owners come from the attendee list** | "Someone", "everyone" and people who were not there give no owner; the action is flagged `NEEDS OWNER`, not assigned |
| **Gaps are flagged, not filled** | "before the next sync" gives no date; the action is flagged `NEEDS DATE` for a person |
| **Nothing is lost silently** | Rejected items are listed in the draft with the reason |
| **Draft until a named person approves** | Same approval gate and audit log as module 01 |

## Run it (no key needed)
```bash
python data/synthetic/meetings.py
python -m modules.m02_meeting_actions.run --notes data/synthetic/meetings/2026-03-02.txt
python -m modules.m02_meeting_actions.run --approve out/actions_2026-03-02_DRAFT.md --approver "Your Name"
python -m modules.m02_meeting_actions.eval.run_eval          # reproduces the numbers below
```
Live model: `pip install anthropic`, set `ANTHROPIC_API_KEY` (and optionally `PM_AI_MODEL`), add `--live`; for the eval,
`run_eval --live --runs 5` (up to 10 runs, 8 model calls per run).

## Your own notes
A plain text file: three header lines, a blank line, then the notes (one sentence or bullet per line).
```
Meeting: Weekly programme sync
Date: 2026-03-02
Attendees: Priya, Marcus, Sofia

Action: Priya to send the contract by Friday.
Marcus said he will chase the bank by Wednesday.
```
The draft is written to `out/actions_<date>_DRAFT.md`. Two meetings on the same date overwrite each other: use different `--out` folders.

## Results (reproduce with `run_eval`)
8 synthetic meetings, 29 hand-labelled actions. The labels were written independently of the date code. Actions are matched to labels by their source sentence.

| Measure | Rule baseline | Tag |
|---|---|---|
| Recall (actions found) | 31.0% (9/29) | 🟢 measured |
| Precision (reported actions that are real) | 100% | 🟢 measured |
| Owner correct, of those found | 100% | 🟢 measured |
| Due date correct, of those found | 88.9% (8/9) | 🟢 measured |
| All correct end to end, of all 29 | 27.6% | 🟢 measured |
| Recall on `Action:` lines / on ordinary prose | 100% / 0% | 🟢 measured |
| Live model (claude-sonnet-5-5, 3 runs, 8 meetings, 29 actions) | recall 100%, precision 100%, all correct 100%, grounding 100% (identical in all 3 runs) | 🟢 measured, but see caveat |

**Read before trusting.** The baseline only reads lines that start with `Action:`, so it finds every templated action and none of the commitments written as ordinary
sentences. That is the gap a model is meant to close, and it is deliberately wide: this is a stress test, not a typical meeting. The baseline also misses one date ("next Friday"
with no preposition). The data is synthetic and small (29 actions, one action is 3.4 points); the live model scored 100% on every run, which on a set this small (and written by the same author as the prompt, never held out) shows it handles these patterns, not that it will on real meetings. Held-out cases are tracked as AGPMO-41.
Real meetings are messier: speaker names, interruptions, two people on one action, deadlines stated across several sentences. None of that is covered.

**Not built, on purpose.** This module never writes to Jira, email or a calendar. Creating tickets from approved actions is a planned step that would need its own approval gate and dry run.

## Files
`facts.py` date rules and parsing, `agent.py` prompt, checker and draft, `run.py` CLI, `eval/run_eval.py`, `SETUP.md`, `AGENT_CONTRACT.md`. Tests: `tests/test_m02.py`.
