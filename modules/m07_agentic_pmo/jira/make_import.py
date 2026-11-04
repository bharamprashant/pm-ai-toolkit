"""Generate the Jira CSV import for the Agentic PMO orchestrator build (project key AGPMO).

  python modules/m07_agentic_pmo/jira/make_import.py     # writes agpmo_import.csv and validates the plan

The plan lives in PLAN below. Edit it, re-run, re-import. Dependencies are written as 'depends on'
and exported as Jira 'Blocks' links (A blocks B means B depends on A), so Jira's blocked-by view
and any dependency-graph agent can read them.
Story points are planning estimates by the author, not measurements.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

OUT = Path(__file__).parent / "agpmo_import.csv"

EPICS = {
    1: ("Foundations", "Agent contracts, shared schemas and the multi-agent audit trail."),
    2: ("Dependency graph engine", "Turn Jira issue links into a graph: ready work, cycles, critical path."),
    3: ("Planner agent", "Propose a sequenced plan from the graph; verify it respects every dependency."),
    4: ("Risk agent", "Flag slipping dependencies from dates and comment text; measure false alarms."),
    5: ("Reporter agent", "Executive status built from Planner and Risk output (reuses module 01)."),
    6: ("Governance reviewer", "Approval gates, permission checks, contract review, standards mapping."),
    7: ("Evaluation", "Synthetic program, labelled cases, single-agent vs multi-agent comparison."),
    8: ("Docs and publishing", "Setup guide, architecture, demo, write-up and release."),
}

# id, epic, summary, component, version, points, priority, sprint, labels, depends_on, acceptance criteria
S = [
    (101, 1, "Define agent contracts for Planner, Risk, Reporter and Governance reviewer", "Orchestrator", "v0.1", 3, "High", 1, ["contract"], [], "One contract per agent: purpose, allowed, not allowed, human decisions, stop conditions. Reviewed against governance/AGENT_CONTRACT_TEMPLATE.md."),
    (102, 1, "Define shared JSON message schema between agents", "Orchestrator", "v0.1", 3, "High", 1, [], [101], "Schema validated in code; invalid messages rejected with a logged reason."),
    (103, 1, "Extend audit log for multi-agent runs (agent, step, input hash)", "Governance reviewer", "v0.1", 3, "High", 1, ["governance"], [102], "Every agent step appends one audit line; log is append-only."),
    (104, 1, "Spike: choose orchestration pattern (coordinator vs peer agents)", "Orchestrator", "v0.1", 2, "Medium", 1, ["spike"], [], "One-page decision record with the trade-offs and the pattern chosen."),
    (201, 2, "Parse Jira issue links into a dependency graph", "Orchestrator", "v0.1", 5, "High", 1, [], [102], "Graph built from 'is blocked by' links in a CSV export; unit tested."),
    (202, 2, "Detect and report dependency cycles", "Orchestrator", "v0.1", 3, "Medium", 1, [], [201], "A cyclic synthetic program is flagged with the cycle path."),
    (203, 2, "Compute ready-to-start items and critical path", "Orchestrator", "v0.2", 5, "High", 2, [], [201], "Ready list and critical path match hand-checked answers on 3 programs."),
    (204, 2, "Unit tests with synthetic programs including a cycle case", "Eval harness", "v0.2", 3, "Medium", 2, [], [202, 203], "Tests run in CI."),
    (301, 3, "Planner baseline: rule-based sequencing", "Planner agent", "v0.2", 3, "High", 2, ["baseline"], [203], "Produces a dependency-respecting order; scored in the eval."),
    (302, 3, "Planner model version proposes a plan from the graph", "Planner agent", "v0.3", 5, "High", 3, [], [301, 102], "Model returns the plan as JSON per the shared schema."),
    (303, 3, "Verifier: plan must respect all blocked-by links", "Planner agent", "v0.3", 3, "High", 3, ["guardrail"], [302], "A plan that violates a link is rejected and the baseline is used, flagged."),
    (304, 3, "Measure plan validity on synthetic programs", "Eval harness", "v0.3", 3, "Medium", 4, ["eval"], [303], "Validity rate for baseline and model published with tag measured."),
    (401, 4, "Risk baseline: overdue, blocked and stale rules", "Risk agent", "v0.2", 3, "High", 2, ["baseline"], [102], "Reuses facts from module 01; scored in the eval."),
    (402, 4, "Risk model reads comments and dependency context", "Risk agent", "v0.3", 5, "High", 3, [], [401, 203], "Cites only ticket keys present in the data."),
    (403, 4, "False-alarm and miss rates on labelled cases", "Eval harness", "v0.3", 3, "High", 4, ["eval"], [402], "Precision, recall and false-alarm rate published with known limits."),
    (501, 5, "Integrate module 01 as the Reporter agent", "Reporter agent", "v0.2", 2, "Medium", 2, [], [102], "Reporter runs behind the shared schema."),
    (502, 5, "Reporter uses Planner and Risk outputs", "Reporter agent", "v0.3", 3, "Medium", 3, [], [302, 402], "Report shows plan status and risks with cited keys."),
    (503, 5, "Executive brief format with decisions needed", "Reporter agent", "v0.3", 2, "Low", 4, [], [502], "One-page brief; RED items list a decision."),
    (601, 6, "Approval gate: nothing is final without a named approver", "Governance reviewer", "v0.1", 3, "Highest", 1, ["governance"], [103], "Approving with an empty name fails; approval is logged."),
    (602, 6, "Permission check: agents may only call allowed tools", "Governance reviewer", "v0.3", 5, "High", 3, ["governance"], [101], "A disallowed tool call is blocked and logged."),
    (603, 6, "Reviewer agent checks outputs against contracts", "Governance reviewer", "v0.3", 5, "High", 4, ["governance"], [601, 602], "Contract violations are flagged before a draft is shown."),
    (604, 6, "Map controls to the PMI AI standard and the EU AI Act", "Governance reviewer", "v1.0", 3, "Medium", 5, ["docs", "governance"], [603], "Mapping table in governance/ with one control per principle."),
    (701, 7, "Build synthetic program (30+ issues, links, comments)", "Eval harness", "v0.2", 5, "High", 2, ["eval"], [], "Fictional program, no real company data."),
    (702, 7, "Label expected plans, risks and RAG", "Eval harness", "v0.2", 3, "High", 2, ["eval"], [701], "Labels stored as JSON; author-labelled limit stated."),
    (703, 7, "End-to-end eval: single agent vs multi-agent", "Eval harness", "v0.3", 5, "Highest", 4, ["eval"], [304, 403, 502], "One command reproduces every published number."),
    (704, 7, "Failure-injection tests (missing data, conflicting instructions, bad link)", "Eval harness", "v1.0", 3, "High", 5, ["eval", "guardrail"], [703], "Each failure is handled safely and logged."),
    (801, 8, "Write SETUP.md following the setup standard", "Docs & setup", "v1.0", 3, "High", 5, ["docs"], [703], "Steps followed once on a clean machine; untested steps marked."),
    (802, 8, "Architecture diagram and decision log", "Docs & setup", "v1.0", 2, "Medium", 5, ["docs"], [603], "Diagram matches the code."),
    (803, 8, "Record a 2-minute demo", "Docs & setup", "v1.0", 2, "Medium", 5, ["docs"], [703], "Shows a run, an approval and the audit log."),
    (804, 8, "Write-up: what worked, what broke", "Docs & setup", "v1.0", 2, "Medium", 5, ["docs"], [703], "Includes the real eval numbers and known limits."),
    (805, 8, "Publish release; add links to CVs and portfolio", "Docs & setup", "v1.0", 1, "Low", 5, ["docs"], [801, 804], "Release tagged; links live."),
]
VERSIONS = ["v0.1", "v0.2", "v0.3", "v1.0"]
COMPONENTS = {s[3] for s in S}


def validate() -> list[str]:
    errs, ids = [], {s[0] for s in S}
    ver = {v: i for i, v in enumerate(VERSIONS)}
    by = {s[0]: s for s in S}
    for s in S:
        if s[1] not in EPICS: errs.append(f"{s[0]}: unknown epic {s[1]}")
        if s[4] not in ver: errs.append(f"{s[0]}: unknown version {s[4]}")
        for d in s[9]:
            if d not in ids: errs.append(f"{s[0]}: depends on missing {d}"); continue
            if ver[by[d][4]] > ver[s[4]]: errs.append(f"{s[0]}: depends on {d} from a later version")
            if by[d][7] > s[7]: errs.append(f"{s[0]}: depends on {d} scheduled in a later sprint")
    # cycle check (DFS)
    state: dict[int, int] = {}
    def dfs(n):
        state[n] = 1
        for d in by[n][9]:
            if d in by:
                if state.get(d) == 1: errs.append(f"cycle through {n} and {d}")
                elif d not in state: dfs(d)
        state[n] = 2
    for n in by:
        if n not in state: dfs(n)
    return errs


def build_rows():
    blocks: dict[int, list[int]] = {}
    for s in S:
        for d in s[9]:
            blocks.setdefault(d, []).append(s[0])   # d blocks s
    max_b = max(len(v) for v in blocks.values())
    header = ["Issue Id", "Issue Type", "Summary", "Description", "Parent Id", "Component/s",
              "Fix Version/s", "Priority", "Story Points", "Labels", "Labels", "Labels"] + ["Outward issue link (Blocks)"] * max_b
    rows = [header]
    for eid, (name, desc) in EPICS.items():
        rows.append([eid, "Epic", name, desc, "", "", "", "Medium", "", "", "", ""] + [""] * max_b)
    for sid, epic, summ, comp, ver, pts, prio, sprint, labels, deps, ac in S:
        lab = (labels + [f"sprint-{sprint}"])[:3] + [""] * 3
        out = blocks.get(sid, [])
        itype = "Task" if "spike" in labels else "Story"
        rows.append([sid, itype, summ, f"Acceptance: {ac}", epic, comp, ver, prio, pts, *lab[:3]] + out + [""] * (max_b - len(out)))
    return rows


def main():
    errs = validate()
    if errs:
        print("PLAN INVALID:\n  " + "\n  ".join(errs)); sys.exit(1)
    rows = build_rows()
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    pts = sum(s[5] for s in S)
    per = {n: sum(s[5] for s in S if s[7] == n) for n in range(1, 6)}
    print(f"wrote {OUT.name}: {len(EPICS)} epics, {len(S)} stories, {pts} points; per sprint {per}")


if __name__ == "__main__":
    main()
