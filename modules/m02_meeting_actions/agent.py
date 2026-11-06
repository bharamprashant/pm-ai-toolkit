"""Meeting-to-action agent: notes -> model (or rules) proposes actions -> checker -> DRAFT for a human.

Pipeline
1. facts.parse_meeting      deterministic: title, date, attendees, lines
2. LLM.complete_json        proposes {"actions": [{"owner","task","due_phrase","quote"}]}
3. check_items()            rejects anything not grounded: quote must be in the notes word for word,
                            owner must be an attendee (or null), the due words must be inside the quote
4. facts.resolve_due        CODE turns the due words into a date, or None (never guessed)
5. render()                 writes a DRAFT; a named person approves later (core.audit)
"""
from __future__ import annotations

import json
import re

from core.llm import LLM, OfflineBaseline
from modules.m02_meeting_actions.facts import Meeting, normalise, resolve_due

SYSTEM = """You extract action items from meeting notes. You receive ATTENDEES, MEETING_DATE and NOTES. Rules:
- An action item is a commitment or assignment to do something. Decisions, status updates, questions and
  things already done are NOT action items.
- quote: copy the one sentence from NOTES that contains the action, exactly as written.
- owner: the attendee who will do it, using the name as written in ATTENDEES. If no single attendee is named
  (for example "someone", "everyone", or a person not in ATTENDEES), use null. Never guess an owner.
- due_phrase: copy the words that give the deadline, exactly as written in the quote (for example "by Friday").
  If the sentence gives no deadline, use null. Never write a calendar date yourself and never guess one.
- task: a short plain description of the work.
Return JSON: {"actions": [{"owner": "...", "task": "...", "due_phrase": "...", "quote": "..."}]}"""

_ACTION_LINE = re.compile(r"^\s*action\s*:\s*(.+)$", re.I)
_DUE_TAIL = re.compile(r"\b((?:by|on|before|for|in)\s+[^.]+?|today|tomorrow)\s*\.?$", re.I)


def _baseline_fn(system: str, user: str) -> dict:
    """Offline stand-in: only lines that start with 'Action:' (a template many teams use). It cannot read prose."""
    data = json.loads(user)
    names = {a.lower(): a for a in data["ATTENDEES"]}
    out = []
    for line in data["NOTES"].splitlines():
        m = _ACTION_LINE.match(line)
        if not m:
            continue
        rest = m.group(1).strip()
        first = rest.split(" ", 1)[0].strip(",.").lower()
        due = _DUE_TAIL.search(rest)
        out.append({"owner": names.get(first), "task": rest, "due_phrase": due.group(1).strip() if due else None,
                    "quote": line.strip()})
    return {"actions": out}


def baseline() -> LLM:
    return OfflineBaseline(_baseline_fn)


def check_items(items: list, meeting: Meeting) -> tuple[list[dict], list[dict]]:
    """Grounding guardrail. Returns (accepted, rejected). A rejected item is shown to the reviewer, never as an action."""
    body = normalise(meeting.body)
    canon = {a.lower(): a for a in meeting.attendees}
    accepted, rejected, seen = [], [], set()
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        quote = str(it.get("quote") or "").strip()
        owner = it.get("owner")
        phrase = it.get("due_phrase")
        reason = None
        if not quote or normalise(quote) not in body:
            reason = "quote is not in the notes"
        elif owner not in (None, "") and str(owner).strip().lower() not in canon:
            reason = f"owner {owner!r} is not an attendee"
        elif phrase and normalise(str(phrase)) not in normalise(quote):
            reason = "due words are not in the quote"
        elif normalise(quote) in seen:
            reason = "duplicate of an earlier action"
        if reason:
            rejected.append({"quote": quote, "owner": owner, "reason": reason})
            continue
        seen.add(normalise(quote))
        owner = canon[str(owner).strip().lower()] if owner not in (None, "") else None
        due = resolve_due(phrase, meeting.date)
        flags = ([] if owner else ["owner"]) + ([] if due else ["date"])
        accepted.append({"owner": owner, "task": str(it.get("task") or quote).strip(), "due_phrase": phrase or None,
                         "due": due.isoformat() if due else None, "quote": quote,
                         "status": "OK" if not flags else "NEEDS " + "+".join(f.upper() for f in flags)})
    return accepted, rejected


def assess(llm: LLM, meeting: Meeting) -> dict:
    user = json.dumps({"ATTENDEES": meeting.attendees, "MEETING_DATE": meeting.date.isoformat(),
                       "NOTES": meeting.body}, indent=1)
    result = llm.complete_json(SYSTEM, user)
    fallback = False
    if not isinstance(result.get("actions"), list):
        # Fail safe: an unusable answer is replaced by the rule baseline, flagged.
        result, fallback = _baseline_fn(SYSTEM, user), True
    accepted, rejected = check_items(result["actions"], meeting)
    return {"actions": accepted, "rejected": rejected, "proposed": len(result["actions"]), "fallback": fallback}


def render(meeting: Meeting, res: dict, model: str) -> str:
    ok = [a for a in res["actions"] if a["status"] == "OK"]
    open_ = [a for a in res["actions"] if a["status"] != "OK"]
    esc = lambda s: str(s).replace("|", "/")
    lines = [
        f"# Meeting actions - {meeting.title} ({meeting.date.isoformat()})", "",
        "STATUS: DRAFT - not approved",
        f"Generated by: {model}{' (fallback to rules: the model answer was unusable)' if res['fallback'] else ''}. "
        "Dates are resolved by code from the words in the notes; the model only finds and words the actions. "
        "Every action quotes the notes. Nothing was guessed: a missing owner or date is flagged below.", "",
        f"Attendees: {', '.join(meeting.attendees)}", "", "## Actions", "",
        "| Owner | Action | Due | Source |", "|---|---|---|---|",
    ]
    lines += [f"| {a['owner']} | {esc(a['task'])} | {a['due']} ({esc(a['due_phrase'])}) | \"{esc(a['quote'])}\" |" for a in ok] \
        or ["| - | none found | - | - |"]
    lines += ["", "## Needs clarification (owner or date missing)", ""]
    lines += [f"- {a['status']}: {esc(a['task'])} - owner: {a['owner'] or '?'}, due: {a['due'] or '?'} "
              f"(words: {esc(a['due_phrase']) if a['due_phrase'] else 'none'}). Source: \"{esc(a['quote'])}\"" for a in open_] or ["- None."]
    lines += ["", "## Rejected by the checker (not actions; shown so nothing is silently lost)", ""]
    lines += [f"- {r['reason']}: \"{esc(r['quote'])}\"" for r in res["rejected"]] or ["- None."]
    return "\n".join(lines) + "\n"
