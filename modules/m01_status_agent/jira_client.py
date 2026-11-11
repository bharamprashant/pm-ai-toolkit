"""Optional READ-ONLY Jira Cloud connector.

Credentials come only from environment variables on the machine running this:
  JIRA_BASE_URL   e.g. https://your-site.atlassian.net
  JIRA_EMAIL      the Atlassian account email
  JIRA_API_TOKEN  create at id.atlassian.com -> Security -> API tokens
Never paste a token into chat, a notebook or a commit. This client only issues GET requests.

STATUS: written against Atlassian's documented Jira Cloud REST v3 search endpoint but NOT yet
exercised against a live site (no credentials were available when it was built). Treat the
first run as a test and report field-mapping problems.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

FIELDS = "summary,status,priority,assignee,components,duedate,updated,customfield_10016,comment,issuelinks"


def _auth_header() -> str:
    email, token = os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"]
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def fetch(jql: str, limit: int = 200) -> list[dict]:
    base = os.environ["JIRA_BASE_URL"].rstrip("/")
    url = f"{base}/rest/api/3/search/jql?" + urllib.parse.urlencode({"jql": jql, "fields": FIELDS, "maxResults": limit})
    req = urllib.request.Request(url, headers={"Authorization": _auth_header(), "Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec - fixed https URL from env
        return json.load(resp).get("issues", [])


def _adf_text(node) -> str:
    """Flatten Atlassian Document Format to plain text."""
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return " ".join(_adf_text(c) for c in node.get("content", []))
    return ""


def to_rows(issues: list[dict]) -> list[dict]:
    rows = []
    for it in issues:
        f = it["fields"]
        comments = (f.get("comment") or {}).get("comments", [])
        last = _adf_text(comments[-1]["body"]).strip() if comments else ""
        blocked = ",".join(
            l["inwardIssue"]["key"] for l in f.get("issuelinks", [])
            if l.get("type", {}).get("inward") == "is blocked by" and "inwardIssue" in l)
        comps = f.get("components") or []
        rows.append({
            "Key": it["key"], "Summary": f["summary"], "Status": f["status"]["name"],
            "Priority": (f.get("priority") or {}).get("name", "Medium"),
            "Assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
            "Workstream": comps[0]["name"] if comps else "Unassigned",
            "Story Points": int(f.get("customfield_10016") or 0),
            "Due Date": f.get("duedate") or "2099-12-31",
            "Updated": f["updated"][:10], "Last Comment": last, "Blocked By": blocked,
        })
    return rows


def export_csv(jql: str, out: str | Path) -> Path:
    import csv
    rows = to_rows(fetch(jql))
    out = Path(out)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return out
