"""CLI for module 01.

  python -m modules.m01_status_agent.run --input data/synthetic/snapshots/2026-03-20.csv --as-of 2026-03-20
  python -m modules.m01_status_agent.run ... --live            # uses ANTHROPIC_API_KEY
  python -m modules.m01_status_agent.run --approve out/status_2026-03-20_DRAFT.md --approver "Your Name"
  python -m modules.m01_status_agent.run --jira-jql 'project = NW' --export out/jira.csv   # read-only export
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from core.audit import AuditLog, approve, fingerprint
from core.llm import AnthropicLLM
from modules.m01_status_agent import agent
from modules.m01_status_agent.facts import compute_facts, load_issues


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input")
    p.add_argument("--as-of")
    p.add_argument("--program", default="Northwind Digital Onboarding")
    p.add_argument("--out", default="out")
    p.add_argument("--live", action="store_true", help="use the Anthropic API instead of the offline baseline")
    p.add_argument("--approve", metavar="DRAFT")
    p.add_argument("--approver", default="")
    p.add_argument("--jira-jql")
    p.add_argument("--export")
    a = p.parse_args(argv)
    out = Path(a.out)
    log = AuditLog(out / "audit.jsonl")

    if a.jira_jql:
        from modules.m01_status_agent.jira_client import export_csv
        path = export_csv(a.jira_jql, a.export or out / "jira_export.csv")
        log.record("system", "jira_export_readonly", file=str(path))
        print(f"exported {path}")
        return 0

    if a.approve:
        final = approve(a.approve, a.approver, log)
        print(f"approved -> {final}")
        return 0

    if not (a.input and a.as_of):
        p.error("--input and --as-of are required")
    as_of = date.fromisoformat(a.as_of)
    llm = AnthropicLLM() if a.live else agent.baseline()
    facts = compute_facts(load_issues(a.input), as_of)
    results = {ws: agent.assess(llm, f) for ws, f in facts.items()}
    report = agent.render(as_of, a.program, results, facts, llm.name)
    out.mkdir(parents=True, exist_ok=True)
    draft = out / f"status_{as_of.isoformat()}_DRAFT.md"
    draft.write_text(report, encoding="utf-8")
    log.record("agent:" + llm.name, "draft_created", draft=draft.name, sha=fingerprint(report),
               rejected=[w for w, r in results.items() if not r.get("verified", True)])
    print(report)
    print(f"draft saved to {draft} - review it, then run with --approve to finalise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
