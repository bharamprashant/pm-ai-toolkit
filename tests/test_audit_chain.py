"""The audit log is hash-chained: editing or deleting an earlier line is detected."""
import json

import pytest

from core.audit import AuditLog, approve, head_hash, main as audit_main, verify_approved, verify_chain


def _log(tmp_path, n=4):
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(n):
        log.record("system", "step", n=i)
    return log


def test_clean_log_verifies_and_head_matches_record_return(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    last = None
    for i in range(3):
        last = log.record("system", "step", n=i)
    r = verify_chain(log.path)
    assert r["entries"] == 3 and r["head"] == last == head_hash(log.path)


def test_empty_or_missing_log_is_fine(tmp_path):
    assert verify_chain(tmp_path / "nope.jsonl")["entries"] == 0


def test_edited_line_is_detected(tmp_path):
    log = _log(tmp_path)
    lines = log.path.read_text().splitlines()
    e = json.loads(lines[1]); e["n"] = 99
    lines[1] = json.dumps(e, sort_keys=True)
    log.path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="line 3"):
        verify_chain(log.path)


def test_deleted_middle_line_is_detected(tmp_path):
    log = _log(tmp_path)
    lines = log.path.read_text().splitlines()
    del lines[1]
    log.path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="chain broken"):
        verify_chain(log.path)


def test_removed_last_line_is_detected_only_with_the_saved_head(tmp_path):
    log = _log(tmp_path)
    saved = head_hash(log.path)
    lines = log.path.read_text().splitlines()[:-1]
    log.path.write_text("\n".join(lines) + "\n")
    assert verify_chain(log.path)["entries"] == 3          # the known limit: nothing after it to break
    with pytest.raises(ValueError, match="anchored"):
        verify_chain(log.path, saved)


def test_unchained_line_among_chained_lines_is_detected(tmp_path):
    log = _log(tmp_path, 2)
    with log.path.open("a") as fh:
        fh.write(json.dumps({"ts": "x", "actor": "a", "action": "forged"}) + "\n")
    with pytest.raises(ValueError, match="no chain link"):
        verify_chain(log.path)


def test_older_unchained_lines_at_the_start_are_tolerated_and_reported(tmp_path):
    p = tmp_path / "audit.jsonl"
    p.write_text(json.dumps({"ts": "x", "actor": "a", "action": "old"}) + "\n")
    AuditLog(p).record("system", "new")
    r = verify_chain(p)
    assert r["entries"] == 2 and r["legacy_unprotected"] == 1


def test_a_tampered_log_blocks_publishing_an_approved_report(tmp_path):
    draft = tmp_path / "status_2026-03-20_DRAFT.md"
    draft.write_text("STATUS: DRAFT - not approved\nbody\n")
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("agent:x", "draft_created", draft=draft.name)
    final = approve(draft, "Pat Approver", log)
    assert verify_approved(final, log.path)
    lines = log.path.read_text().splitlines()
    e = json.loads(lines[0]); e["actor"] = "someone-else"
    lines[0] = json.dumps(e, sort_keys=True)
    log.path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="integrity check"):
        verify_approved(final, log.path)


def test_cli_verify_and_head(tmp_path, capsys):
    log = _log(tmp_path)
    assert audit_main(["verify", str(log.path)]) == 0
    assert "chain intact" in capsys.readouterr().out
    assert audit_main(["verify", str(log.path), "--head", "wrong"]) == 1
    assert audit_main(["head", str(log.path)]) == 0
