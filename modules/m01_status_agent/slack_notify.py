"""Slack messages for the status agent, sent through a Slack Incoming Webhook.

Same rules as email (see notify.py):
  * the approved report is posted only after `verify_approved` passes (not a draft, logged, unchanged);
  * nothing is posted unless you pass --send; the default writes the exact JSON payload to out/outbox/;
  * the webhook URL is a secret: environment variable only, never logged, and only https://hooks.slack.com/services/...
    URLs are accepted, so a mistyped or malicious URL cannot receive your report.

Two webhooks, so a draft can never land in the stakeholder channel by accident:
  SLACK_REVIEW_WEBHOOK_URL   where "draft ready for review" goes (the approver's private channel); no fallback
  SLACK_WEBHOOK_URL          where the APPROVED report goes (the stakeholder channel)

All text that comes from tickets or the model is escaped, so a comment containing <!channel> or <https://...|link>
shows as plain text and cannot ping the workspace.

STATUS: payloads and sending are unit-tested with a simulated HTTP call; NOT yet tested against a real Slack workspace.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from core.audit import AuditLog
from modules.m01_status_agent.notify import Report

ICON = {"RED": ":red_circle:", "AMBER": ":large_orange_circle:", "GREEN": ":large_green_circle:"}
MAX_SECTION = 2800        # Slack allows 3000 characters in a section; keep headroom
MAX_BLOCKS = 50           # Slack's limit per message
SLACK_ID_RE = re.compile(r"^[UW][A-Z0-9]{6,}$")


def esc(text: str) -> str:
    """Escape the three characters Slack treats specially, so ticket text cannot create mentions or links."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _trunc(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def validate_webhook(url: str) -> str:
    u = urlparse(url)
    if u.scheme != "https" or u.hostname != "hooks.slack.com" or not u.path.startswith("/services/"):
        raise ValueError("not a Slack incoming-webhook URL (expected https://hooks.slack.com/services/...)")
    return url


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": _trunc(text, MAX_SECTION)}}


def _context(text: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": _trunc(text, 1900)}]}


def _overall(rep: Report) -> str:
    c = rep.counts()
    return (f"*Overall:*   {ICON['RED']} {c['RED']} RED     {ICON['AMBER']} {c['AMBER']} AMBER     "
            f"{ICON['GREEN']} {c['GREEN']} GREEN")


def _row_block(r) -> dict:
    tag = r.rag + (" (fallback)" if r.fallback else "")
    return _section(f"{ICON[r.rag]} *{esc(r.workstream)}*  ·  {tag}\n{esc(r.why)}\n"
                    f"_Done {esc(r.done)}  ·  Overdue {esc(r.overdue)}  ·  Blocked {esc(r.blocked)}  ·  Stale {esc(r.stale)}_")


def _cap(blocks: list[dict]) -> list[dict]:
    if len(blocks) <= MAX_BLOCKS:
        return blocks
    keep = blocks[: MAX_BLOCKS - 2]
    keep.append(_context(f"{len(blocks) - len(keep)} more block(s) not shown; see the full report."))
    keep.append(blocks[-1])
    return keep


def publish_payload(rep: Report, cfg: dict) -> dict:
    attention = [r for r in rep.rows if r.rag != "GREEN"]
    greens = [r.workstream for r in rep.rows if r.rag == "GREEN"]
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": _trunc(f"{rep.program} - weekly status {rep.as_of}", 140)}},
        _section(_overall(rep)),
    ]
    if rep.decisions:
        blocks.append(_section("*Decisions needed*\n" + "\n".join(f"•  {esc(d)}" for d in rep.decisions)))
    if attention:
        blocks.append({"type": "divider"})
        blocks += [_row_block(r) for r in attention]
    else:
        blocks.append(_section("Every workstream is on track."))
    if greens:
        blocks.append(_context("On track: " + ", ".join(esc(g) for g in greens)))
    owners = cfg.get("workstream_owners", {})
    mention = cfg.get("slack", {}).get("mention_owners", True)
    asks = []
    for r in attention:
        o = owners.get(r.workstream)
        if not o:
            continue
        who = f"<@{o['slack_id']}>" if mention and o.get("slack_id") else esc(o["name"])
        asks.append(f"•  {who}  ·  {esc(r.workstream)} ({r.rag})")
    if asks:
        blocks.append(_section("*Check-ins requested*  Please reply in this thread with: the cause, your recovery plan and "
                               "the date it is back on track, and any help or decision you need.\n" + "\n".join(asks)))
    blocks.append(_context(f"Approved by {esc(rep.approved_by)} on {esc(rep.approved_at)}  ·  counts and dates are computed by code  ·  "
                           f"colour and reason from {esc(rep.generated_by or 'the status agent')}, reviewed by a person before posting  ·  "
                           "(fallback) = the AI answer was rejected by the checker and simple rules were used"))
    return {"text": f"{rep.program} status {rep.as_of}: {rep.headline()}", "blocks": _cap(blocks)}


def review_payload(rep: Report, draft_name: str, approver_name: str) -> dict:
    attention = [r for r in rep.rows if r.rag != "GREEN"]
    approve_cmd = f'python3 -m modules.m01_status_agent.run --approve out/{draft_name} --approver "{approver_name}"'
    publish_cmd = f"python3 -m modules.m01_status_agent.notify publish --final out/{draft_name.replace('DRAFT', 'FINAL')} --via both"
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": _trunc(f"Review needed: {rep.program} status {rep.as_of}", 140)}},
        _section(_overall(rep) + "\n*This is a DRAFT.* Nothing has been sent to anyone else."),
    ]
    if attention:
        blocks.append(_section("*Needs your attention*\n" + "\n".join(
            f"{ICON[r.rag]} *{esc(r.workstream)}*: {esc(r.why)}" for r in attention)))
    blocks.append(_section("*Next steps (a person does these)*\n1. Read the draft file.\n2. Approve it:\n```" + approve_cmd
                           + "```\n3. Publish it:\n```" + publish_cmd + "```"))
    blocks.append(_context("DRAFT - not approved. Do not forward."))
    return {"text": f"[Review needed] {rep.program} status {rep.as_of} (draft: {rep.headline()})", "blocks": _cap(blocks)}


def review_items(rep: Report, cfg: dict, draft_name: str) -> list[tuple[str, dict, str]]:
    return [("slack_review_request", review_payload(rep, draft_name, cfg["approver"]["name"]), "SLACK_REVIEW_WEBHOOK_URL")]


def publish_items(rep: Report, cfg: dict) -> list[tuple[str, dict, str]]:
    return [("slack_publish", publish_payload(rep, cfg), "SLACK_WEBHOOK_URL")]


def _post(url: str, payload: dict) -> None:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:  # nosec - URL validated to hooks.slack.com
        body = resp.read().decode("utf-8", "replace").strip()
        if resp.status != 200 or body != "ok":
            raise RuntimeError("unexpected response from Slack")


def deliver(items: list[tuple[str, dict, str]], report_name: str, report_sha: str, log: AuditLog,
            outbox: Path, send: bool, environ: dict) -> tuple[int, int, list[str]]:
    """Write payload files (dry run) or post. Returns (ok, failed, notes)."""
    ok = failed = 0
    notes: list[str] = []
    if not send:
        outbox.mkdir(parents=True, exist_ok=True)
        for kind, payload, _env in items:
            path = outbox / f"{kind}.json"
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            log.record("system", "slack_prepared", kind=kind, report=report_name, report_sha=report_sha, file=path.name)
            ok += 1
        return ok, failed, notes
    for kind, payload, env in items:
        url = environ.get(env)
        if not url:
            if kind == "slack_review_request":
                notes.append(f"Slack review request skipped: {env} is not set (the draft is never posted to the stakeholder channel)")
                continue
            raise RuntimeError(f"to post to Slack, set environment variable {env} to your Slack incoming-webhook URL")
        try:
            _post(validate_webhook(url), payload)
            log.record("system", "slack_sent", kind=kind, report=report_name, report_sha=report_sha)
            ok += 1
        except Exception as exc:  # the URL is a secret and error text can echo it: log the class only
            log.record("system", "slack_failed", kind=kind, error=type(exc).__name__, report=report_name)
            failed += 1
    return ok, failed, notes
