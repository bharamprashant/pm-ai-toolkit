# Setup guide - Status & executive report agent

Follows [docs/SETUP_STANDARD.md](../../docs/SETUP_STANDARD.md).

## 1. What you get
A weekly status report (one row per workstream with RAG, counts and a reason) written as a DRAFT markdown file.
A named person approves it; every step is logged in `out/audit.jsonl`.

## 2. Prerequisites
| Need | Notes | Cost |
|---|---|---|
| Python 3.10+ | `python3 --version` | free |
| This repo | `git clone https://github.com/bharamprashant/pm-ai-toolkit` | free |
| A Jira Cloud site | A **personal** free site with fake data is enough to learn on | free tier |
| An Anthropic API key | Only for `--live`; the offline baseline needs none | pay per use |

## 3. Step-by-step setup
1. **Clone and enter the repo.** `git clone ... && cd pm-ai-toolkit`
2. **Create the synthetic data.** `python data/synthetic/generate.py` - expect "wrote 4 snapshots and labels for 24 cases".
3. **Run the tests.** `pip install pytest && python -m pytest -q` - expect `the tests passed`.
4. **Run the dry run** (section 5) before connecting anything.
5. **Create a Jira Cloud site** (skip if you have one): sign up at atlassian.com, create a software project, add 15-30 fake issues.
6. **Prepare the Jira data the agent reads** (section 6).
7. **Create credentials** (section 4) and export them as environment variables.
8. **Export from Jira** (read-only) and run the agent on the export.
9. **Review the DRAFT, then approve it.**
10. **Schedule it** (section 7).

## 4. Credentials
| Secret | Where to create | Where to store | Never |
|---|---|---|---|
| `JIRA_API_TOKEN` | id.atlassian.com -> Security -> Create and manage API tokens | shell environment, or a CI secret | commit it, paste it in chat, put it in a notebook |
| `JIRA_EMAIL`, `JIRA_BASE_URL` | your Atlassian account and site URL | environment | - |
| `ANTHROPIC_API_KEY` | console.anthropic.com | environment, or a CI secret | commit it |

```bash
export JIRA_BASE_URL="https://your-site.atlassian.net"
export JIRA_EMAIL="you@example.com"
export JIRA_API_TOKEN="..."        # typed into your own terminal only
```
Use a token from an account that can only **read** the project. The connector sends GET requests only.

## 5. Dry run on synthetic data (no accounts)
```bash
python -m modules.m01_status_agent.run --input data/synthetic/snapshots/2026-03-20.csv --as-of 2026-03-20
python -m modules.m01_status_agent.run --approve out/status_2026-03-20_DRAFT.md --approver "Your Name"
python -m modules.m01_status_agent.eval.run_eval
```
Expected: a table of six workstreams, a `STATUS: DRAFT` header, then `approved -> ..._FINAL.md`, and an eval showing 87.5% for the baseline.

## 6. Connect your own Jira
The agent needs these fields per issue. Check your project provides them:
| Agent field | Jira source | If missing |
|---|---|---|
| Workstream | first **Component** of the issue | Add components, one per workstream |
| Story Points | custom field `customfield_10016` | The id differs by site; find yours at `https://<site>/rest/api/3/field` and edit `FIELDS` and `to_rows` in `jira_client.py` |
| Blocked By | issue link whose inward text is "is blocked by" | Use the "Blocks" link type |
| Last Comment | newest comment, flattened to text | Ask the team to log blockers as comments |
| Due Date | `duedate` | Items without one are treated as far future |

Then export and run:
```bash
python -m modules.m01_status_agent.run --jira-jql 'project = ABC AND sprint in openSprints()' --export out/jira.csv
python -m modules.m01_status_agent.run --input out/jira.csv --as-of $(date +%F) --program "My Program"
```
Add `--live` to use the model instead of the rule baseline.

## 7. Schedule it, and email the right people

### 7.1 The daily flow and its timing
Nothing is scheduled until you set it up (7.5). The times below are the recommended pattern, in Stockholm time; only the
08:00 start is set by the schedule, the other times are a working agreement for people.

| Time (Stockholm) | Who | What happens |
|---|---|---|
| 08:00, Mon-Fri | the schedule | pulls the data (read-only Jira or a CSV), computes facts, drafts the report, sends **only the approver** a "Review needed" email and/or Slack message |
| 08:00 - 10:00 | the approver | reads the draft, approves it with their name |
| right after approval | the approver | runs `notify publish --via both --send` |
| immediately | the tool | refuses anything unapproved or edited; otherwise emails the sponsor and steering group (exec view), emails the delivery lead (full view), posts to the stakeholder Slack channel, and asks each Red or Amber owner for a check-in |
| 10:00 | the reminder schedule | if the draft is still unapproved 2 hours after it was created, nudges **the approver only** (email and/or private Slack) with the exact commands |
| 12:00 | the reminder schedule | if still unapproved 4 hours after creation, sends the configured **escalation contact** a short note: the headline counts and who is being waited for. The report itself is not shared |
| later that day | owners | reply with cause, recovery plan and date; replies go to the approver by email, or in the Slack thread |

Time zones for CI: GitHub schedules use UTC and ignore daylight saving. 08:00 in Stockholm is 07:00 UTC in winter (CET) and
06:00 UTC in summer (CEST), so a CI cron of `30 6 * * 1-5` fires at 07:30 in winter and 08:30 in summer. Cron on your own
machine can use `CRON_TZ=Europe/Stockholm` and then follows daylight saving.

```
08:00 every weekday  scheduled run (cron or CI)
   |  pulls the data, computes facts, drafts the report
   |  messages ONLY the approver: "Draft ready for review" (email with the draft attached, and/or a private Slack channel)
   v
approver reads the draft, approves it with their name           (a person)
   |
   v
publish step (a person runs it)   verifies the approval and that the file is unchanged, then
   |  - emails the sponsor/steering group a short exec view (RED and AMBER only + decisions needed)
   |  - emails the delivery lead the full team view
   |  - posts the approved report to the stakeholder Slack channel
   |  - asks the owner of every RED or AMBER workstream for a check-in (email, and an @mention in Slack)
```
The scheduled run never approves and never messages stakeholders. That is deliberate: nothing reaches other people
until a named person has approved it. Reminders (7.7) only nag the approver and, later, tell an escalation contact that a report is late.

### 7.2 Set up the recipients
1. `cp config/stakeholders.example.json config/stakeholders.json`
2. Edit the file: the approver, each stakeholder with `"audience": "exec"` or `"team"`, and the owner of each workstream.
   The file is git-ignored because it holds email addresses. Never commit it.
3. Each address is validated; a bad address or a name containing a line break is rejected with a clear message.

### 7.3 Try it safely first (dry run, sends nothing)
```bash
INPUT_CSV=data/synthetic/snapshots/2026-03-20.csv AS_OF_DATE=2026-03-20 PROGRAM_NAME="Northwind" \
  modules/m01_status_agent/run_scheduled.sh
python3 -m modules.m01_status_agent.run --approve out/status_2026-03-20_DRAFT.md --approver "Pat Approver"
python3 -m modules.m01_status_agent.notify publish --final out/status_2026-03-20_FINAL.md
```
Expected: ready-to-read `.eml` files in `out/outbox/` (open them in any mail app). Try `notify publish` on the DRAFT file or after
editing the FINAL file: it must print `REFUSED` and exit with code 2.

### 7.4 Turn on real sending
Set these in the environment of the machine that sends (never in a file in the repo), then add `--send`:
| Variable | Meaning |
|---|---|
| `SMTP_HOST` | your mail server, for example `smtp.office365.com` or `smtp.gmail.com` |
| `SMTP_PORT` | optional; 587 for STARTTLS (default), 465 for SSL |
| `SMTP_SECURITY` | optional: `starttls` (default) or `ssl`. Unencrypted sending is not supported |
| `SMTP_USER`, `SMTP_PASSWORD` | your login. Many providers require an app password, not your normal password |
| `SMTP_FROM` | the sender address, for example `status@yourcompany.com` |

Then: `python3 -m modules.m01_status_agent.notify publish --final out/status_DATE_FINAL.md --send`.
For the scheduled review request to the approver, add `SEND_EMAIL=1` to the schedule's environment.

### 7.5 Run it on a schedule
Cron on a server or always-on computer (weekdays 08:00 Stockholm time; `CRON_TZ` is supported by cronie but not every cron):
```
CRON_TZ=Europe/Stockholm
0 8 * * 1-5  JIRA_JQL='project = ABC' PROGRAM_NAME='My Program' SEND_EMAIL=1 /path/to/pm-ai-toolkit/modules/m01_status_agent/run_scheduled.sh
```
Cron does **not** inherit your terminal's environment. The Jira and SMTP variables must be set inside the job or a wrapper
script that only you can read. A weekly schedule is the same line with `1` instead of `1-5`. A laptop that is asleep at 08:00
will skip the run, so use an always-on machine or the CI option.

CI option: copy `automation/weekly-status.yml.example` to `.github/workflows/`, add the secrets listed in it, and keep the human
approval step. GitHub schedules run in UTC and can start a few minutes late.

### 7.7 Reminders and escalation for an unapproved draft
`run_reminder.sh` finds today's draft in `out/` and runs `notify remind`. It decides from the audit log, not from the clock alone:

| Condition | What happens |
|---|---|
| draft is already approved, or younger than `after_hours` (default 2) | nothing is sent |
| older than `after_hours` | **level 1**: reminder to the approver, with the approve and publish commands |
| older than `escalate_after_hours` (default 4) | **level 2**: to the escalation contact (`escalation` in the config): headline counts and the approver's name only, and the message says the report "has not been shared with you" |
| a level was already really sent | not repeated (dry runs never count, so testing does not block the real reminder) |

Slack uses `SLACK_REVIEW_WEBHOOK_URL` for level 1 and the optional `SLACK_ESCALATION_WEBHOOK_URL` for level 2; a missing one is skipped with a note, never rerouted to the stakeholder channel.
Set the thresholds in `config/stakeholders.json` (`reminders`) or with `--after-hours` / `--escalate-after-hours`.

Try it with no mail server (the `--now` flag moves the clock so you can see each level):
```bash
python3 -m modules.m01_status_agent.notify remind --draft out/status_DATE_DRAFT.md --via both --now 2026-03-27T10:30:00+00:00
```
Schedule it with the same persistent `out/` folder as the morning run, for example:
```
CRON_TZ=Europe/Stockholm
0 10,12 * * 1-5  OUT_DIR=/path/to/out SEND_EMAIL=1 /path/to/pm-ai-toolkit/modules/m01_status_agent/run_reminder.sh
```
It needs the same environment variables as 7.4 and 7.6 set inside the job. It cannot work in the stateless CI template, because a fresh CI runner
has no draft and no log to look at. Reminders go out whether or not anyone is reachable; they do not replace a deputy approver.

### 7.6 Slack: set it up (about 10 minutes)
Slack messages go through an **Incoming Webhook**: no bot token, no OAuth, and the tool can only post, never read.
You may need a Slack workspace admin to allow the app. This path has **not** been tested against a real workspace.

1. Go to https://api.slack.com/apps and click **Create New App -> From scratch**. Name it "Status Agent" and pick your workspace.
2. In the left menu open **Incoming Webhooks** and switch **Activate Incoming Webhooks** on.
3. Click **Add New Webhook to Workspace**, pick the **stakeholder channel** (for example `#program-status`), and allow it. Copy the
   URL, which starts with `https://hooks.slack.com/services/`.
4. Repeat step 3 for a **private channel only the approver can see** (for example `#status-review`) and copy that second URL.
   Two webhooks keep a draft from ever landing in the stakeholder channel by mistake. The review message is never sent to the
   stakeholder webhook, even if the review one is missing.
5. Set both as environment variables on the machine that sends (never in a file in the repo, never in chat):
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."          # approved report, stakeholder channel
   export SLACK_REVIEW_WEBHOOK_URL="https://hooks.slack.com/services/..."   # draft review request, private channel
   ```
6. Optional, to @mention owners: in Slack open the person's profile -> the three dots -> **Copy member ID** (looks like `U01ABCDEF2`)
   and add it as `"slack_id"` to that owner in `config/stakeholders.json`. Without it the owner is named but not pinged.
7. Dry run first. It writes the exact message to `out/outbox/slack_publish.json`:
   ```bash
   python3 -m modules.m01_status_agent.notify publish --final out/status_DATE_FINAL.md --via slack
   ```
   You can paste that JSON into Slack's Block Kit Builder (https://app.slack.com/block-kit-builder) to preview it.
8. Send for real: add `--send`. Use `--via both` to send email and Slack together. For the scheduled review request set
   `NOTIFY_VIA=slack` (or `both`) and `SEND_EMAIL=1` in the schedule's environment.

What the Slack message looks like: a header with the program and date, the Red/Amber/Green counts, a **Decisions needed** list,
one block per Red or Amber workstream (reason with ticket keys and the four counts), a line naming the on-track workstreams, a
**Check-ins requested** list that @mentions the owners and asks them to reply in the thread, and a footer with the approver and time.
Text that comes from tickets is escaped, so a comment containing `<!channel>` appears as plain text and cannot ping the workspace.

Security notes: a webhook URL is a password for posting to that channel. Treat it like one. If it leaks, revoke it in the app's
Incoming Webhooks page and add a new one. The tool refuses any URL that is not `https://hooks.slack.com/services/...`, never
logs the URL, and logs only the error class if posting fails. Everyone in the channel can read the report, so choose the
channel accordingly.

## 8. Governance checklist
- [ ] I read `AGENT_CONTRACT.md` and accept its limits.
- [ ] The token is read-only and stored as a secret.
- [ ] `out/audit.jsonl` is being kept.
- [ ] A named approver reviews every report before it is shared.
- [ ] `config/stakeholders.json` lists only the right people and is not committed.
- [ ] I ran the publish step as a dry run and read the emails and the Slack JSON before the first `--send`.
- [ ] The Slack webhook URLs are in the environment or a CI secret, the review one points to a private channel, and I know who can read the stakeholder channel.
- [ ] SMTP credentials are in the environment or a CI secret, never in a file in the repo.
- [ ] I am using synthetic or explicitly approved data.

## 9. Verify it worked
A correct run prints six workstreams, shows no "(fallback)" marks unless the model was rejected, creates a DRAFT file, and appends a `draft_created` line to the audit log. Re-run the eval after any threshold, prompt or model change.

## 10. Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: 'JIRA_EMAIL'` | environment variables not set in this shell | export them again |
| HTTP 401 / 403 from Jira | wrong email, expired token or no project access | recreate the token; check project permissions |
| Every workstream shows "Unassigned" | issues have no Components | add components or change the mapping |
| Story points all 0 | different custom field id | see section 6 |
| "(fallback)" in the report | the model cited a ticket not in the data, or an invalid RAG | read the rejection reason at the end of that row's text in the report (`audit.jsonl` lists only which workstreams were rejected); tighten the prompt; re-run the eval |
| `REFUSED: ...` from `notify publish` | the report is a draft, has no approval record, or was edited after approval | approve the draft (or re-approve) and publish the file the approval created; never edit a FINAL file |
| `to send for real, set environment variable(s): SMTP_HOST...` | `--send` without mail settings | set the variables in section 7.4 or drop `--send` for a dry run |
| `email_failed` in the log | login, port or network problem | check host, port, security and app password; the log shows only the error type, so test the same settings in a mail client |
| `not a Slack incoming-webhook URL` (logged as `slack_failed` with `ValueError`) | the variable holds something other than `https://hooks.slack.com/services/...` | copy the URL again from the app's Incoming Webhooks page |
| `to post to Slack, set environment variable SLACK_WEBHOOK_URL` | `--via slack --send` without the variable | set it (7.6) or drop `--send` |
| `Slack review request skipped: SLACK_REVIEW_WEBHOOK_URL is not set` | no private review webhook configured | add it, or the draft is simply not posted to Slack (by design it never falls back to the stakeholder channel) |
| `slack_failed` in the log (HTTP 403/404 behind it) | the webhook was revoked, the app was removed, or the channel was archived | create a new webhook; the log shows only the error type |
| `invalid stakeholder config` | bad address or audience in the config | fix the lines it lists |
| `ANTHROPIC_API_KEY is not set` | `--live` without a key | export the key or drop `--live` |

## 11. Status of this guide
| Step | Run for real? |
|---|---|
| Sections 3.1-3.4, 5 (synthetic dry run, tests, eval) | yes |
| Sections 3.5-3.8, 6 (live Jira connector) | **yes - run against a live Jira Cloud site on 11 Nov 2026 with a read-only token (35 stories exported, report built)** |
| `--live` model run | yes, 5 runs per prompt on the synthetic eval (2026-11-06); not on real data |
| Section 7.3 (dry-run emails, refusal of drafts and edited files) | yes, run end to end on a clean checkout |
| Section 7.4 real sending | **tested on the wire against a local stand-in SMTP server with STARTTLS and certificate checking on (`tests/test_smtp_wire.py`); not tested against a real provider such as Gmail or Office 365** |
| Section 7.6 Slack payloads, escaping, webhook checks, dry run | yes (unit tests and an end-to-end dry run) |
| Section 7.6 posting to a real Slack workspace | **no - simulated HTTP call in unit tests only** |
| Section 7.7 reminder levels, de-duplication, escalation privacy (unit tests and a simulated-clock dry run) | yes |
| Section 7.7 real sending of reminders, and the reminder cron line | **no - untested against a real server or scheduler** |
| Section 7.5 cron line and CI template | **no - untested** |
