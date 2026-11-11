"""Wire-level email test against a LOCAL stand-in mail server (real SMTP + STARTTLS over a self-signed cert).

What this proves: the scheduled script and `notify publish` really open an SMTP connection, negotiate TLS with
certificate verification ON, and deliver the right messages to the right people (review request to the approver only;
the report to stakeholders only after approval). What it does NOT prove: delivery through a real provider (Gmail,
Office 365...), their authentication rules, spam filtering, or that a real clock (cron/CI) fires the schedule.
Skipped automatically when aiosmtpd or openssl is not installed (python3 -m pip install aiosmtpd).
"""
import json
import os
import shutil
import ssl
import subprocess
import sys
from pathlib import Path

import pytest

aiosmtpd = pytest.importorskip("aiosmtpd")
from aiosmtpd.controller import Controller  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")


class Sink:
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append((envelope.rcpt_tos, envelope.content.decode("utf-8", "replace")))
        return "250 OK"


@pytest.fixture()
def smtp(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-keyout", str(key),
                    "-out", str(cert), "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                   check=True, capture_output=True)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    sink = Sink()
    ctl = Controller(sink, hostname="127.0.0.1", port=free_port, server_hostname="localhost", tls_context=ctx,
                     require_starttls=True)
    ctl.start()
    yield sink, free_port, cert
    ctl.stop()


def _env(port, cert, **extra):
    env = {**os.environ, "SMTP_HOST": "localhost", "SMTP_PORT": str(port), "SMTP_FROM": "agent@example.com",
           "SSL_CERT_FILE": str(cert), "PYTHONPATH": str(ROOT)}
    env.pop("SMTP_USER", None)
    env.update(extra)
    return env


def _config(tmp_path):
    cfg = tmp_path / "stakeholders.json"
    cfg.write_text(json.dumps({
        "approver": {"name": "Approver", "email": "approver@example.com"},
        "stakeholders": [{"name": "Sponsor", "email": "sponsor@example.com", "audience": "exec"},
                         {"name": "Lead", "email": "lead@example.com", "audience": "team"}],
    }))
    return cfg


def test_scheduled_run_emails_only_the_approver_then_publish_emails_stakeholders_after_approval(smtp, tmp_path):
    sink, port, cert = smtp
    out, cfg = tmp_path / "out", _config(tmp_path)
    env = _env(port, cert, INPUT_CSV=str(ROOT / "data/synthetic/snapshots/2026-03-20.csv"), AS_OF_DATE="2026-03-20",
               OUT_DIR=str(out), NOTIFY_CONFIG=str(cfg), SEND_EMAIL="1", PROGRAM_NAME="Wire test")
    r = subprocess.run(["bash", str(ROOT / "modules/m01_status_agent/run_scheduled.sh")], env=env, cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    assert [m[0] for m in sink.messages] == [["approver@example.com"]]      # scheduled run: approver only
    assert "DRAFT" in sink.messages[0][1]

    r = subprocess.run([sys.executable, "-m", "modules.m01_status_agent.run", "--approve",
                        str(out / "status_2026-03-20_DRAFT.md"), "--approver", "Real Person", "--out", str(out)],
                       env=env, cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    r = subprocess.run([sys.executable, "-m", "modules.m01_status_agent.notify", "publish", "--final",
                        str(out / "status_2026-03-20_FINAL.md"), "--config", str(cfg), "--out", str(out), "--send"],
                       env=env, cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    got = sorted(rcpt for m in sink.messages[1:] for rcpt in m[0])
    assert got == ["lead@example.com", "sponsor@example.com"]
    log = (out / "audit.jsonl").read_text()
    assert log.count('"email_sent"') == 3 and "email_failed" not in log


def test_tls_verification_is_on_a_server_we_do_not_trust_is_refused(smtp, tmp_path):
    sink, port, _cert = smtp
    out, cfg = tmp_path / "out", _config(tmp_path)
    env = _env(port, tmp_path / "other-cert-not-trusted.pem",
               INPUT_CSV=str(ROOT / "data/synthetic/snapshots/2026-03-20.csv"), AS_OF_DATE="2026-03-20",
               OUT_DIR=str(out), NOTIFY_CONFIG=str(cfg), SEND_EMAIL="1")
    env["SSL_CERT_FILE"] = str(tmp_path / "missing.pem")
    subprocess.run(["bash", str(ROOT / "modules/m01_status_agent/run_scheduled.sh")], env=env, cwd=ROOT,
                   capture_output=True, text=True)
    assert sink.messages == []
    assert "email_failed" in (out / "audit.jsonl").read_text()
