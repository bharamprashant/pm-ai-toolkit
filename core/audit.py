"""Append-only, hash-chained audit log and human approval gate.

Governance rule used by every module: an agent produces a DRAFT. Nothing is
treated as final until a named human approves it, and every step is logged.

Each log line stores `prev`, the SHA-256 of the line before it ("genesis" for the first). Editing or deleting an
earlier line breaks the chain, and `verify_chain` reports where. This makes the log TAMPER-EVIDENT, not tamper-proof:
  * someone who rewrites the whole file and recomputes every hash is not detected, and
  * removing the LAST lines is detected only if you kept the head hash somewhere else (`--head`).
Keep a copy of the head hash outside this folder (the approve commands print it) to close the second gap.

  python -m core.audit verify out/audit.jsonl [--head HASH]
  python -m core.audit head out/audit.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


GENESIS = "genesis"


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _lines(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    return [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def head_hash(path: str | Path) -> str:
    """Hash of the last line: the value to keep somewhere else to detect removed lines."""
    lines = _lines(path)
    return _line_hash(lines[-1]) if lines else GENESIS


class AuditLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, actor: str, action: str, **details) -> str:
        """Append one entry, chained to the previous line. Returns the new head hash."""
        entry = {"ts": _now(), "actor": actor, "action": action, **details, "prev": head_hash(self.path)}
        line = json.dumps(entry, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return _line_hash(line)


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


def verify_chain(path: str | Path, expected_head: str | None = None) -> dict:
    """Check that no earlier line was edited or removed. Raises ValueError at the first break.

    Lines written before chaining existed (no `prev`) are tolerated only at the start of the file, and are not protected.
    """
    prev, legacy, chained = GENESIS, 0, 0
    for n, line in enumerate(_lines(path), 1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError(f"audit log line {n} is not valid JSON") from None
        if "prev" not in entry:
            if chained:
                raise ValueError(f"audit log line {n} has no chain link after chained lines (a line was altered)")
            legacy += 1
        elif entry["prev"] != prev:
            raise ValueError(f"audit log chain broken at line {n}: an earlier line was edited or removed")
        else:
            chained += 1
        prev = _line_hash(line)
    if expected_head is not None and prev != expected_head:
        raise ValueError("audit log does not end where it was anchored: lines were removed or added at the end")
    return {"entries": legacy + chained, "legacy_unprotected": legacy, "head": prev}


def verify_approved(final_path: str | Path, log_path: str | Path) -> dict:
    """Return the approval record only if the file is approved, logged, and unchanged since approval.

    Raises ValueError otherwise. Anything that is sent to other people must pass this first.
    """
    final = Path(final_path)
    text = final.read_text(encoding="utf-8")
    if Path(log_path).exists():
        try:
            verify_chain(log_path)
        except ValueError as exc:
            raise ValueError(f"the audit log failed its integrity check: {exc}") from None
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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Check or print the head of a hash-chained audit log.")
    p.add_argument("command", choices=["verify", "head"])
    p.add_argument("log")
    p.add_argument("--head", help="the head hash you saved earlier; detects removed last lines")
    a = p.parse_args(argv)
    if a.command == "head":
        print(head_hash(a.log))
        return 0
    try:
        r = verify_chain(a.log, a.head)
    except ValueError as exc:
        print(f"FAILED: {exc}")
        return 1
    note = f" ({r['legacy_unprotected']} older lines are not protected)" if r["legacy_unprotected"] else ""
    print(f"OK: {r['entries']} entries, chain intact{note}. head {r['head']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
