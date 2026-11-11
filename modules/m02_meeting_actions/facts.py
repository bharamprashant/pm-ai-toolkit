"""Deterministic parts of module 02: parse the notes, resolve date words to calendar dates.

The model never writes a date. It copies the words ("by Friday"); this code turns them into a date with fixed rules,
or returns None when the words cannot be resolved. A missing date is flagged for a human, never guessed.

Rules (meeting on `d`, weeks run Monday to Sunday):
  today / tomorrow                 d / d+1
  <weekday>, this <weekday>        the first such day AFTER d
  next <weekday>                   that weekday in the FOLLOWING week
  end of (this) week               the Friday of d's week
  end of next week                 the Friday of the following week
  in N days / in N weeks           d + N days / d + 7N days
  YYYY-MM-DD, 13 March, March 13   that date (this year); not accepted if before d
Anything else ("before the next sync", "when he gets a chance", "soon") -> None.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

WEEKDAYS = {n: i for i, n in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}
MONTHS = {n: i + 1 for i, n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                          "august", "september", "october", "november", "december"])}
_WD = "|".join(WEEKDAYS)
_MO = "|".join(MONTHS)


@dataclass
class Meeting:
    title: str
    date: date
    attendees: list[str]
    lines: list[str]

    @property
    def body(self) -> str:
        return "\n".join(self.lines)


def parse_meeting(text: str) -> Meeting:
    head, _, body = text.partition("\n\n")
    fields = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()
    for need in ("meeting", "date", "attendees"):
        if need not in fields:
            raise ValueError(f"meeting notes need a '{need.title()}:' header line")
    attendees = [a.strip() for a in fields["attendees"].split(",") if a.strip()]
    return Meeting(fields["meeting"], date.fromisoformat(fields["date"]), attendees,
                   [ln.strip() for ln in body.splitlines() if ln.strip()])


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _friday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday()) + timedelta(days=4)


def resolve_due(phrase: str | None, meeting_date: date) -> date | None:
    if not phrase or not phrase.strip():
        return None
    p = normalise(phrase).rstrip(".")
    p = re.sub(r"^(by|on|before|until|for|due)\s+", "", p)
    p = re.sub(r"^the\s+(?=end of)", "", p)   # "by the end of next week" (found by the held-out set)
    d = meeting_date
    if p == "today":
        return d
    if p == "tomorrow":
        return d + timedelta(days=1)
    if re.fullmatch(r"end of (this )?week", p):
        return _friday_of_week(d)
    if p == "end of next week":
        return _friday_of_week(d) + timedelta(days=7)
    m = re.fullmatch(rf"next ({_WD})", p)
    if m:
        return d - timedelta(days=d.weekday()) + timedelta(days=7 + WEEKDAYS[m.group(1)])
    m = re.fullmatch(rf"(?:this )?({_WD})", p)
    if m:
        delta = (WEEKDAYS[m.group(1)] - d.weekday()) % 7 or 7
        return d + timedelta(days=delta)
    m = re.fullmatch(r"in (\d{1,3}) (day|days|week|weeks)", p)
    if m:
        n = int(m.group(1)) * (7 if m.group(2).startswith("week") else 1)
        return d + timedelta(days=n)
    found = None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
        try:
            found = date.fromisoformat(p)
        except ValueError:
            return None
    else:
        m = re.fullmatch(rf"(\d{{1,2}})(?:st|nd|rd|th)? ({_MO})", p) or re.fullmatch(rf"({_MO}) (\d{{1,2}})(?:st|nd|rd|th)?", p)
        if m:
            day, mon = (m.group(1), m.group(2)) if m.group(1).isdigit() else (m.group(2), m.group(1))
            try:
                found = date(d.year, MONTHS[mon], int(day))
            except ValueError:
                return None
    return found if found and found >= d else None
