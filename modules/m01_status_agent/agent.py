"""Status agent: facts -> judgment (model or baseline) -> verified report.

Pipeline
1. facts.compute_facts      deterministic counts, dates, lists
2. LLM.complete_json        returns {"rag","rationale","cited_keys"} per workstream
3. verify()                 rejects anything not grounded in the facts
4. render()                 writes a DRAFT markdown report (human approves later)
"""
from __future__ import annotations

import json
from datetime import date

from core.llm import LLM, OfflineBaseline
from modules.m01_status_agent.facts import WorkstreamFacts, rule_rag

RAGS = {"GREEN", "AMBER", "RED"}

SYSTEM = """You are a program-management analyst writing a weekly RAG status for ONE workstream.
You receive FACTS computed by code. Rules:
- Use only the FACTS. Never invent ticket keys, dates, owners or numbers.
- Judge RAG as GREEN, AMBER or RED. Read open_item_comments: a comment can reveal a risk
  (for example an unavailable dependency) that dates alone do not show, or show that an
  overdue item does not matter (for example a cancelled duplicate).
- cited_keys must be ticket keys that appear in FACTS and that support your rationale.
- rationale: at most 2 plain sentences for an executive reader.
Return JSON: {"rag": "...", "rationale": "...", "cited_keys": ["..."]}"""


# Prompt v2 adds one severity rule. It was written AFTER the first live eval showed the model rating
# stated-blocker weeks AMBER where the labels say RED, and it is scored on the same 24 cases, so any gain
# it shows is optimistic (tuned on the test set). Production keeps v1 (SYSTEM) until v2 is validated on new cases.
SYSTEM_V2 = SYSTEM.replace(
    "- cited_keys must be",
    "- Severity: if a comment says a dependency, vendor, environment or decision the work needs is unavailable or\n"
    "  delayed, and gives no firm date by which it will arrive, rate the workstream RED, not AMBER, even when every\n"
    "  ticket is on time. If the comment gives a firm date that still leaves the work on time, do not raise it.\n"
    "- cited_keys must be")
assert SYSTEM_V2 != SYSTEM
PROMPTS = {"v1": SYSTEM, "v2": SYSTEM_V2}


def _baseline_fn(system: str, user: str) -> dict:
    """Offline stand-in: rule-based RAG. It deliberately cannot read comment text."""
    facts = json.loads(user)["FACTS"]
    f = WorkstreamFacts(
        workstream=facts["workstream"], as_of=date.fromisoformat(facts["as_of"]),
        total=facts["total_issues"], done=facts["done"], points_done=facts["points_done"],
        points_total=facts["points_total"], overdue=facts["overdue"],
        overdue_critical=facts["overdue_critical"], blocked=facts["blocked"],
        stale=[k for key, v in facts.items() if key.startswith("stale") for k in v],
        unowned=facts.get("unassigned_open", []),
        open_dated=0 if facts.get("no_schedule_data") else 1,
    )
    rag, why = rule_rag(f)
    cited = f.overdue_critical or f.overdue or f.blocked or f.stale
    return {"rag": rag, "rationale": f"Rule check: {why}.", "cited_keys": cited[:4]}


def baseline() -> LLM:
    return OfflineBaseline(_baseline_fn)


def verify(result: dict, facts: WorkstreamFacts) -> tuple[bool, str]:
    """Grounding guardrail. Returns (ok, reason)."""
    if result.get("rag") not in RAGS:
        return False, f"invalid rag {result.get('rag')!r}"
    if not str(result.get("rationale", "")).strip():
        return False, "empty rationale"
    known = set(facts.comments) | set(facts.overdue) | set(facts.blocked) | set(facts.stale)
    bad = [k for k in result.get("cited_keys", []) if k not in known]
    if bad:
        return False, f"cited keys not in facts: {bad}"
    return True, "ok"


def _apply_data_gaps(result: dict, facts: WorkstreamFacts) -> dict:
    """Code guard: missing schedule data or owners can never produce a clean GREEN, whatever the model said."""
    notes = []
    if facts.no_schedule and "no schedule data" not in result["rationale"]:
        notes.append("No due dates on open items, so on-time delivery cannot be judged.")
    if facts.unowned and "have no owner" not in result["rationale"]:
        notes.append(f"No owner on: {', '.join(facts.unowned)}.")
    if notes:
        if result["rag"] == "GREEN":
            result["rag"] = "AMBER"
        result["rationale"] = (result["rationale"].rstrip() + " " + " ".join(notes)).strip()
    return result


def assess(llm: LLM, facts: WorkstreamFacts, system: str = SYSTEM) -> dict:
    user = json.dumps({"FACTS": facts.to_dict()}, indent=1)
    result = llm.complete_json(system, user)
    ok, reason = verify(result, facts)
    if not ok:
        # Fail safe: never publish an ungrounded judgment. Fall back to the rule baseline, flagged.
        fb = _baseline_fn(system, user)
        fb["rationale"] += f" [fallback: model output rejected - {reason}]"
        fb["verified"] = False
        return _apply_data_gaps(fb, facts)
    result["verified"] = True
    return _apply_data_gaps(result, facts)


def render(as_of: date, program: str, results: dict[str, dict], facts: dict[str, WorkstreamFacts], model: str) -> str:
    icon = {"GREEN": "GREEN", "AMBER": "AMBER", "RED": "RED"}
    order = {"RED": 0, "AMBER": 1, "GREEN": 2}
    lines = [
        f"# {program} - weekly status ({as_of.isoformat()})",
        "",
        "STATUS: DRAFT - not approved",
        f"Generated by: {model}. Counts and dates are computed by code; the model only judges and explains.",
        "",
        "| Workstream | RAG | Done | Overdue | Blocked | Stale | Why |",
        "|---|---|---|---|---|---|---|",
    ]
    for ws in sorted(results, key=lambda w: (order[results[w]["rag"]], w)):
        r, f = results[ws], facts[ws]
        flag = "" if r.get("verified", True) else " (fallback)"
        lines.append(
            f"| {ws} | {icon[r['rag']]}{flag} | {f.done}/{f.total} | {len(f.overdue)} | {len(f.blocked)} | "
            f"{len(f.stale)} | {r['rationale']} ({', '.join(r['cited_keys']) or 'no keys'}) |"
        )
    reds = [w for w in results if results[w]["rag"] == "RED"]
    decisions = [f"{w}: confirm recovery plan or descope." for w in reds]
    for w in sorted(facts):
        if facts[w].unowned:
            decisions.append(f"{w}: assign an owner to {', '.join(facts[w].unowned)}.")
    lines += ["", "## Decisions needed",
              "\n".join(f"- {d}" for d in decisions) if decisions else "- None this week."]
    return "\n".join(lines) + "\n"
