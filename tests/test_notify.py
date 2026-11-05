"""Tests for approval-gated email. SMTP is simulated; no network and no real mail server is used."""
import json
import smtplib
from datetime import date
from email import message_from_bytes
from pathlib import Path

import pytest

from core.audit import AuditLog, approve, verify_approved
from modules.m01_status_agent import agent, notify
from modules.m01_status_agent.facts import compute_facts, load_issues

DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic"
CFG = {
    "approver": {"name": "Pat Approver", "email": "pat@example.com"},
    "stakeholders": [
        {"name": "Sponsor", "email": "sponsor@example.com", "audience": "exec"},
        {"name": "Lead", "email": "lead@example.com", "audience": "team"},
    ],
    "workstream_owners": {"Payments": {"name": "Pay Owner", "email": "pay@example.com"},
                          "Collections": {"name": "Col Owner", "email": "col@example.com"}},
}


def _make_draft(tmp_path, snap="2026-03-20", comment_red=False):
    as_of = date.fromisoformat(snap)
    facts = compute_facts(load_issues(DATA / "snapshots" / f"{snap}.csv"), as_of)
    llm = agent.baseline()
    results = {ws: agent.assess(llm, f) for ws, f in facts.items()}
    if comment_red:  # simulate a human-reviewed RED so the Decisions section and owner check-in are exercised
        results["Payments"] = {"rag": "RED", "rationale": "Vendor sandbox not before mid-April.",
                               "cited_keys": ["NW-113"], "verified": True}
    text = agent.render(as_of, "Test Program", results, facts, llm.name)
    draft = tmp_path / f"status_{snap}_DRAFT.md"
    draft.write_text(text, encoding="utf-8")
    return draft


def _approved(tmp_path, **kw):
    draft = _make_draft(tmp_path, **kw)
    log = AuditLog(tmp_path / "audit.jsonl")
    return approve(draft, "Pat Approver", log)


def test_parse_report_reads_rows_and_decisions(tmp_path):
    rep = notify.parse_report(_make_draft(tmp_path, comment_red=True).read_text())
    assert rep.program == "Test Program" and rep.as_of == "2026-03-20"
    assert len(rep.rows) == 6 and rep.counts()["RED"] == 1
    assert rep.rows[0].rag == "RED" and rep.decisions and "Payments" in rep.decisions[0]


def test_publish_refuses_a_draft(tmp_path):
    draft = _make_draft(tmp_path)
    with pytest.raises(ValueError, match="not approved"):
        verify_approved(draft, tmp_path / "audit.jsonl")


def test_publish_refuses_a_report_edited_after_approval(tmp_path):
    final = _approved(tmp_path)
    verify_approved(final, tmp_path / "audit.jsonl")  # fine while untouched
    final.write_text(final.read_text().replace("AMBER", "GREEN", 1))
    with pytest.raises(ValueError, match="changed after it was approved"):
        verify_approved(final, tmp_path / "audit.jsonl")


def test_publish_refuses_a_file_with_no_log_record(tmp_path):
    final = _approved(tmp_path)
    (tmp_path / "audit.jsonl").write_text("")
    with pytest.raises(ValueError, match="no approval record"):
        verify_approved(final, tmp_path / "audit.jsonl")


def test_dry_run_writes_eml_files_and_sends_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("SMTP must not be used in a dry run")
    monkeypatch.setattr(smtplib, "SMTP", boom)
    final = _approved(tmp_path, comment_red=True)
    (tmp_path / "cfg.json").write_text(json.dumps(CFG))
    rc = notify.main(["publish", "--final", str(final), "--config", str(tmp_path / "cfg.json"), "--out", str(tmp_path)])
    assert rc == 0
    files = sorted(p.name for p in (tmp_path / "outbox").glob("*.eml"))
    # 2 stakeholders + owner check-ins for Payments (RED) and Collections (AMBER); other AMBER owners are not configured
    assert any("sponsor" in f for f in files) and any("lead" in f for f in files)
    assert any("owner_checkin" in f and "pay-example-com" in f for f in files)
    log = (tmp_path / "audit.jsonl").read_text()
    assert "email_prepared" in log and "email_sent" not in log


def test_exec_view_hides_green_and_team_view_shows_all(tmp_path):
    rep = notify.parse_report(_make_draft(tmp_path, comment_red=True).read_text())
    ex, team = notify.render_text(rep, "exec"), notify.render_text(rep, "team")
    assert "Compliance" not in ex and "Compliance" in team
    assert "DECISIONS NEEDED" in ex and "Payments" in ex


def test_html_is_escaped(tmp_path):
    rep = notify.parse_report(_make_draft(tmp_path).read_text())
    rep.rows[0].why = '<script>alert(1)</script> & more'
    out = notify.render_html(rep, "team")
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_real_send_uses_starttls_login_and_sends_each_message(tmp_path, monkeypatch):
    calls = {"sent": [], "starttls": 0, "login": None}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            calls["host"], calls["port"] = host, port
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self): pass
        def starttls(self, context=None): calls["starttls"] += 1
        def login(self, u, p): calls["login"] = (u, p)
        def send_message(self, m): calls["sent"].append(m["To"])

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    for k, v in {"SMTP_HOST": "smtp.example.com", "SMTP_FROM": "status@example.com",
                 "SMTP_USER": "u", "SMTP_PASSWORD": "p"}.items():
        monkeypatch.setenv(k, v)
    final = _approved(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(CFG))
    rc = notify.main(["publish", "--final", str(final), "--config", str(tmp_path / "cfg.json"),
                      "--out", str(tmp_path), "--send"])
    assert rc == 0 and calls["starttls"] >= 2 and calls["login"] == ("u", "p")
    assert calls["port"] == 587 and len(calls["sent"]) >= 2
    log = (tmp_path / "audit.jsonl").read_text()
    assert "email_sent" in log and '"p"' not in log  # the password is never logged


def test_send_without_smtp_settings_fails_clearly(tmp_path, monkeypatch):
    for k in ("SMTP_HOST", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)
    final = _approved(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(CFG))
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        notify.main(["publish", "--final", str(final), "--config", str(tmp_path / "cfg.json"),
                     "--out", str(tmp_path), "--send"])


def test_failed_send_is_logged_without_error_text_and_exit_code_is_nonzero(tmp_path, monkeypatch):
    class BadSMTP:
        def __init__(self, *a, **k): raise OSError("secret-host-detail")
    monkeypatch.setattr(smtplib, "SMTP", BadSMTP)
    monkeypatch.setenv("SMTP_HOST", "h"); monkeypatch.setenv("SMTP_FROM", "f@example.com")
    final = _approved(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(CFG))
    rc = notify.main(["publish", "--final", str(final), "--config", str(tmp_path / "cfg.json"),
                      "--out", str(tmp_path), "--send"])
    log = (tmp_path / "audit.jsonl").read_text()
    assert rc == 1 and "email_failed" in log and "secret-host-detail" not in log


def test_review_request_goes_only_to_the_approver_with_draft_attached(tmp_path):
    draft = _make_draft(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(CFG))
    rc = notify.main(["review-request", "--draft", str(draft), "--config", str(tmp_path / "cfg.json"),
                      "--out", str(tmp_path)])
    emls = list((tmp_path / "outbox").glob("*.eml"))
    assert rc == 0 and len(emls) == 1 and "pat-example-com" in emls[0].name
    msg = message_from_bytes(emls[0].read_bytes())
    assert "[Review needed]" in msg["Subject"]
    assert any(part.get_filename() == draft.name for part in msg.walk())


def test_config_rejects_bad_address_and_header_injection(tmp_path):
    bad = json.loads(json.dumps(CFG))
    bad["stakeholders"][0]["email"] = "not-an-email"
    bad["stakeholders"][1]["name"] = "Eve\r\nBcc: x@evil.test"
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="invalid"):
        notify.load_config(tmp_path / "bad.json")


def test_publish_on_missing_file_is_a_clear_refusal_not_a_crash(tmp_path, capsys):
    (tmp_path / "cfg.json").write_text(json.dumps(CFG))
    rc = notify.main(["publish", "--final", str(tmp_path / "nope_FINAL.md"),
                      "--config", str(tmp_path / "cfg.json"), "--out", str(tmp_path)])
    assert rc == 2 and "REFUSED" in capsys.readouterr().err


def test_footer_names_the_generator_once_and_is_not_garbled(tmp_path):
    rep = notify.parse_report(_approved(tmp_path).read_text())
    assert rep.generated_by == "offline-baseline"
    footer = notify.render_text(rep, "team").split("--\n")[-1]
    assert footer.count("computed by code") == 1 and "Pat Approver" in footer
