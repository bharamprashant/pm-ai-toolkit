"""Append-only audit log and human approval gate.

Governance rule used by every module: an agent produces a DRAFT. Nothing is
treated as final until a named human approves it, and every step is logged.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AuditLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, actor: str, action: str, **details) -> None:
        entry = {"ts": _now(), "actor": actor, "action": action, **details}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def approve(draft_path: str | Path, approver: str, log: AuditLog) -> Path:
    """Promote draft -> final. Refuses an empty approver name."""
    if not approver.strip():
        raise ValueError("approval requires a named approver")
    draft = Path(draft_path)
    body = draft.read_text(encoding="utf-8")
    final = draft.with_name(draft.name.replace("DRAFT", "FINAL"))
    stamped = body.replace("STATUS: DRAFT - not approved", f"STATUS: APPROVED by {approver} at {_now()}")
    final.write_text(stamped, encoding="utf-8")
    log.record(approver, "approved", draft=draft.name, final=final.name,
               draft_sha=fingerprint(body), final_sha=fingerprint(stamped))
    return final


def read_log(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_approved(final_path: str | Path, log_path: str | Path) -> dict:
    """Return the approval record only if the file is approved, logged, and unchanged since approval.

    Raises ValueError otherwise. Anything that is sent to other people must pass this first.
    """
    final = Path(final_path)
    text = final.read_text(encoding="utf-8")
    if "STATUS: APPROVED by " not in text:
        raise ValueError("report is not approved (still a draft); approve it first")
    entries = [e for e in read_log(log_path) if e.get("action") == "approved" and e.get("final") == final.name]
    if not entries:
        raise ValueError("no approval record for this file in the audit log")
    last = entries[-1]
    if "final_sha" not in last:
        raise ValueError("approval record has no final_sha (approved by an older version); approve the draft again")
    if last["final_sha"] != fingerprint(text):
        raise ValueError("the final report was changed after it was approved; refusing to send")
    return last
