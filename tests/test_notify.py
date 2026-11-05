"""Tests for approval-gated email. SMTP is simulated; no network and no real mail server is used."""
import json
import smtplib
from datetime import date
from email import message_from_bytes, policy
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


# ------------------------------------------------------------------------------------- Slack
import io
import urllib.request

from modules.m01_status_agent import slack_notify

HOOK = "https://hooks.slack.com/services/T000/B000/SECRETSECRET"
SCFG = json.loads(json.dumps(CFG))
SCFG["workstream_owners"]["Payments"]["slack_id"] = "U01ABCDEF2"


class _Resp:
    def __init__(self, status=200, body=b"ok"):
        self.status, self._b = status, body
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_slack_text_from_tickets_is_escaped_so_it_cannot_ping_or_link(tmp_path):
    rep = notify.parse_report(_make_draft(tmp_path, comment_red=True).read_text())
    rep.rows[0].why = "<!channel> see <https://evil.test|click> & <@U999>"
    rep.approved_by, rep.approved_at = "Pat", "2026-03-20T09:00:00+00:00"
    blob = json.dumps(slack_notify.publish_payload(rep, SCFG))
    assert "<!channel>" not in blob and "<https://evil.test" not in blob and "<@U999>" not in blob
    assert "&lt;!channel&gt;" in blob


def test_slack_publish_payload_has_decisions_checkins_mention_and_footer(tmp_path):
    rep = notify.parse_report(_approved(tmp_path, comment_red=True).read_text())
    payload = slack_notify.publish_payload(rep, SCFG)
    blob = json.dumps(payload)
    assert payload["text"].startswith("Test Program status 2026-03-20")
    assert "Decisions needed" in blob and "Check-ins requested" in blob
    assert "<@U01ABCDEF2>" in blob            # configured owner is mentioned
    assert "Col Owner" in blob                # owner without a slack_id is named, not mentioned
    assert "Approved by Pat Approver" in blob
    assert len(payload["blocks"]) <= slack_notify.MAX_BLOCKS


def test_slack_block_count_and_text_length_are_capped():
    blocks = [slack_notify._section("x" * 5000) for _ in range(80)]
    assert all(len(b["text"]["text"]) <= slack_notify.MAX_SECTION for b in blocks)
    assert len(slack_notify._cap(blocks + [slack_notify._context("footer")])) <= slack_notify.MAX_BLOCKS


@pytest.mark.parametrize("url", ["http://hooks.slack.com/services/a/b/c", "https://evil.test/services/a/b/c",
                                 "https://hooks.slack.com.evil.test/services/a", "https://hooks.slack.com/other/a"])
def test_only_real_slack_webhook_urls_are_accepted(url):
    with pytest.raises(ValueError):
        slack_notify.validate_webhook(url)
    assert slack_notify.validate_webhook(HOOK) == HOOK


def test_slack_dry_run_writes_payload_file_and_posts_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network in dry run")))
    final = _approved(tmp_path, comment_red=True)
    (tmp_path / "cfg.json").write_text(json.dumps(SCFG))
    rc = notify.main(["publish", "--final", str(final), "--config", str(tmp_path / "cfg.json"),
                      "--out", str(tmp_path), "--via", "slack"])
    assert rc == 0
    payload = json.loads((tmp_path / "outbox" / "slack_publish.json").read_text())
    assert payload["blocks"][0]["type"] == "header"
    assert not list((tmp_path / "outbox").glob("*.eml"))      # --via slack sends no email
    log = (tmp_path / "audit.jsonl").read_text()
    assert "slack_prepared" in log and "slack_sent" not in log


def test_slack_send_posts_json_and_never_logs_the_webhook_url(tmp_path, monkeypatch):
    seen = {}
    def fake_urlopen(req, timeout=None):
        seen["url"], seen["body"] = req.full_url, json.loads(req.data)
        return _Resp()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", HOOK)
    final = _approved(tmp_path, comment_red=True)
    (tmp_path / "cfg.json").write_text(json.dumps(SCFG))
    rc = notify.main(["publish", "--final", str(final), "--config", str(tmp_path / "cfg.json"),
                      "--out", str(tmp_path), "--via", "slack", "--send"])
    assert rc == 0 and seen["url"] == HOOK and "blocks" in seen["body"]
    assert "SECRETSECRET" not in (tmp_path / "audit.jsonl").read_text()


def test_slack_failure_is_logged_without_error_text_and_exit_code_nonzero(tmp_path, monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("leaks SECRETSECRET")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", HOOK)
    final = _approved(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(SCFG))
    rc = notify.main(["publish", "--final", str(final), "--config", str(tmp_path / "cfg.json"),
                      "--out", str(tmp_path), "--via", "slack", "--send"])
    log = (tmp_path / "audit.jsonl").read_text()
    assert rc == 1 and "slack_failed" in log and "SECRETSECRET" not in log


def test_slack_publish_refuses_draft_and_edited_files_like_email(tmp_path):
    draft = _make_draft(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(SCFG))
    args = ["--config", str(tmp_path / "cfg.json"), "--out", str(tmp_path), "--via", "slack"]
    assert notify.main(["publish", "--final", str(draft), *args]) == 2
    final = _approved(tmp_path, snap="2026-03-27")
    final.write_text(final.read_text().replace("AMBER", "GREEN", 1))
    assert notify.main(["publish", "--final", str(final), *args]) == 2


def test_slack_review_request_needs_its_own_webhook_and_never_falls_back(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", HOOK)
    monkeypatch.delenv("SLACK_REVIEW_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("draft must not be posted")))
    draft = _make_draft(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(SCFG))
    rc = notify.main(["review-request", "--draft", str(draft), "--config", str(tmp_path / "cfg.json"),
                      "--out", str(tmp_path), "--via", "slack", "--send"])
    assert rc == 0 and "SLACK_REVIEW_WEBHOOK_URL is not set" in capsys.readouterr().out


def test_slack_send_without_webhook_variable_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    final = _approved(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(SCFG))
    with pytest.raises(RuntimeError, match="SLACK_WEBHOOK_URL"):
        notify.main(["publish", "--final", str(final), "--config", str(tmp_path / "cfg.json"),
                     "--out", str(tmp_path), "--via", "slack", "--send"])


def test_config_rejects_a_malformed_slack_id(tmp_path):
    bad = json.loads(json.dumps(SCFG))
    bad["workstream_owners"]["Payments"]["slack_id"] = "@payments-owner"
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="slack_id"):
        notify.load_config(tmp_path / "bad.json")


def test_owner_checkin_shows_the_whole_program_headline_not_a_one_row_count(tmp_path):
    rep = notify.parse_report(_approved(tmp_path, comment_red=True).read_text())
    items, _ = notify.publish_messages(rep, CFG, "s@example.com")
    checkin = next(m for k, m in items if k == "owner_checkin" and "Pay Owner" in m["To"])
    body = checkin.get_body(("plain",)).get_content()
    assert rep.headline() in body and "Reason:" in body and ". Please reply" in body


# ------------------------------------------------------------------------------------ reminders
from datetime import datetime, timedelta, timezone

RCFG = json.loads(json.dumps(SCFG))
RCFG["escalation"] = {"name": "Line Manager", "email": "manager@example.com"}


def _draft_with_log(tmp_path):
    """A generated draft plus the draft_created record the real CLI would have written."""
    draft = _make_draft(tmp_path, comment_red=True)
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("agent:offline-baseline", "draft_created", draft=draft.name, sha="abc", rejected=[])
    created = datetime.fromisoformat(json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[-1])["ts"])
    (tmp_path / "cfg.json").write_text(json.dumps(RCFG))
    return draft, created


def _remind(tmp_path, draft, now, *extra):
    return notify.main(["remind", "--draft", str(draft), "--config", str(tmp_path / "cfg.json"), "--out", str(tmp_path),
                        "--now", now.isoformat(), *extra])


def test_no_reminder_before_the_first_threshold(tmp_path, capsys):
    draft, created = _draft_with_log(tmp_path)
    assert _remind(tmp_path, draft, created + timedelta(hours=1)) == 0
    assert "no reminder due" in capsys.readouterr().out
    assert not (tmp_path / "outbox").exists()


def test_first_reminder_goes_only_to_the_approver_with_the_headline_and_commands(tmp_path):
    draft, created = _draft_with_log(tmp_path)
    assert _remind(tmp_path, draft, created + timedelta(hours=2, minutes=5)) == 0
    emls = list((tmp_path / "outbox").glob("*.eml"))
    assert len(emls) == 1 and "reminder_1_pat-example-com" in emls[0].name
    msg = message_from_bytes(emls[0].read_bytes(), policy=policy.default)
    body = msg.get_body(("plain",)).get_content()
    assert "[Reminder]" in msg["Subject"] and "--approve" in body and "stakeholders have not been updated" in body


def test_escalation_goes_to_the_contact_with_the_headline_only(tmp_path):
    draft, created = _draft_with_log(tmp_path)
    assert _remind(tmp_path, draft, created + timedelta(hours=4, minutes=5)) == 0
    names = sorted(p.name for p in (tmp_path / "outbox").glob("*.eml"))
    assert any(n.startswith("reminder_1") for n in names) and any(n.startswith("reminder_2_manager") for n in names)
    esc = message_from_bytes(next((tmp_path / "outbox").glob("reminder_2_*.eml")).read_bytes(), policy=policy.default)
    body = esc.get_body(("plain",)).get_content()
    assert "Overall in the draft:" in body and "NW-113" not in body and "Rule check" not in body and "Payments" not in body
    assert "has not been shared with you" in body


def test_reminders_are_not_repeated_once_really_sent(tmp_path, monkeypatch):
    sent = []
    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self): pass
        def starttls(self, context=None): pass
        def login(self, u, p): pass
        def send_message(self, m): sent.append(m["Subject"])
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_HOST", "h"); monkeypatch.setenv("SMTP_FROM", "f@example.com")
    draft, created = _draft_with_log(tmp_path)
    t = created + timedelta(hours=2, minutes=5)
    assert _remind(tmp_path, draft, t, "--send") == 0 and len(sent) == 1
    assert _remind(tmp_path, draft, t + timedelta(minutes=30), "--send") == 0 and len(sent) == 1   # same level: not again
    assert _remind(tmp_path, draft, created + timedelta(hours=4, minutes=5), "--send") == 0 and len(sent) == 2  # escalation only


def test_a_dry_run_does_not_block_a_later_real_reminder(tmp_path):
    draft, created = _draft_with_log(tmp_path)
    t = created + timedelta(hours=2, minutes=5)
    _remind(tmp_path, draft, t); _remind(tmp_path, draft, t)
    assert (tmp_path / "audit.jsonl").read_text().count("email_prepared") == 2
    entries = notify.read_log(tmp_path / "audit.jsonl")
    levels, _, _ = notify.due_reminders(entries, draft.name, t, 2, 4, True)
    assert levels == [1]


def test_no_reminder_once_the_draft_is_approved(tmp_path, capsys):
    draft, created = _draft_with_log(tmp_path)
    approve(draft, "Pat Approver", AuditLog(tmp_path / "audit.jsonl"))
    assert _remind(tmp_path, draft, created + timedelta(hours=9)) == 0
    assert "already approved" in capsys.readouterr().out and not (tmp_path / "outbox").exists()


def test_reminder_for_a_draft_with_no_log_record_is_refused(tmp_path):
    draft = _make_draft(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(RCFG))
    assert _remind(tmp_path, draft, datetime.now(timezone.utc) + timedelta(hours=9)) == 2


def test_escalation_without_a_configured_contact_says_so_and_still_reminds(tmp_path, capsys):
    draft, created = _draft_with_log(tmp_path)
    (tmp_path / "cfg.json").write_text(json.dumps(SCFG))       # no "escalation" block
    assert _remind(tmp_path, draft, created + timedelta(hours=5)) == 0
    out = capsys.readouterr().out
    assert "no escalation contact is configured" in out
    assert [p.name for p in (tmp_path / "outbox").glob("*.eml")] == ["reminder_1_pat-example-com.eml"]


def test_slack_reminder_uses_the_private_review_webhook_and_escalation_has_its_own(tmp_path, monkeypatch, capsys):
    posted = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: (posted.append(req.full_url), _Resp())[1])
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/STAKEHOLDER/x")
    monkeypatch.setenv("SLACK_REVIEW_WEBHOOK_URL", "https://hooks.slack.com/services/T/REVIEW/x")
    monkeypatch.delenv("SLACK_ESCALATION_WEBHOOK_URL", raising=False)
    draft, created = _draft_with_log(tmp_path)
    assert _remind(tmp_path, draft, created + timedelta(hours=4, minutes=5), "--via", "slack", "--send") == 0
    assert posted == ["https://hooks.slack.com/services/T/REVIEW/x"]        # never the stakeholder webhook
    assert "SLACK_ESCALATION_WEBHOOK_URL is not set" in capsys.readouterr().out


def test_config_rejects_bad_reminder_settings(tmp_path):
    bad = json.loads(json.dumps(RCFG)); bad["reminders"] = {"after_hours": -1}; bad["escalation"]["email"] = "nope"
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="reminders.after_hours"):
        notify.load_config(tmp_path / "bad.json")
