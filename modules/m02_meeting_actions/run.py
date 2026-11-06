"""CLI for module 02.

  python -m modules.m02_meeting_actions.run --notes data/synthetic/meetings/2026-03-02.txt
  python -m modules.m02_meeting_actions.run --notes FILE --live          # uses ANTHROPIC_API_KEY
  python -m modules.m02_meeting_actions.run --approve out/actions_2026-03-02_DRAFT.md --approver "Your Name"
"""
from __future__ import annotations

import argparse
from pathlib import Path

from core.audit import AuditLog, approve, fingerprint
from core.llm import AnthropicLLM
from modules.m02_meeting_actions import agent
from modules.m02_meeting_actions.facts import parse_meeting


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--notes")
    p.add_argument("--out", default="out")
    p.add_argument("--live", action="store_true", help="use the Anthropic API instead of the offline baseline")
    p.add_argument("--approve", metavar="DRAFT")
    p.add_argument("--approver", default="")
    a = p.parse_args(argv)
    out = Path(a.out)
    log = AuditLog(out / "audit.jsonl")
    if a.approve:
        print(f"approved -> {approve(a.approve, a.approver, log)}")
        return 0
    if not a.notes:
        p.error("--notes is required")
    meeting = parse_meeting(Path(a.notes).read_text(encoding="utf-8"))
    llm = AnthropicLLM() if a.live else agent.baseline()
    res = agent.assess(llm, meeting)
    report = agent.render(meeting, res, llm.name)
    out.mkdir(parents=True, exist_ok=True)
    draft = out / f"actions_{meeting.date.isoformat()}_DRAFT.md"
    draft.write_text(report, encoding="utf-8")
    log.record("agent:" + llm.name, "draft_created", draft=draft.name, sha=fingerprint(report),
               accepted=len(res["actions"]), rejected=len(res["rejected"]), fallback=res["fallback"])
    print(report)
    print(f"draft saved to {draft} - review it, then run with --approve to finalise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
