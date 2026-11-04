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
    log.record(approver, "approved", draft=draft.name, final=final.name, draft_sha=fingerprint(body))
    return final
