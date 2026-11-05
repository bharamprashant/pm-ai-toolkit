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

### 7.1 The daily flow
```
08:00 every weekday  scheduled run (cron or CI)
   |  pulls the data (read-only Jira, or a CSV), computes facts, drafts the report
   |  emails ONLY the approver: "Draft ready for review" (draft attached)
   v
approver reads the draft, approves it with their name           (a person)
   |
   v
publish step (a person runs it)   verifies the approval and that the file is unchanged, then
   |  - emails the sponsor/steering group a short exec view (RED and AMBER only + decisions needed)
   |  - emails the delivery lead the full team view
   |  - emails a check-in to the owner of every RED or AMBER workstream, asking for cause,
   |    recovery plan and date, and any help needed (replies go to the approver)
```
The scheduled run never approves and never emails stakeholders. That is deliberate: nothing reaches other people
until a named person has approved it.

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

## 8. Governance checklist
- [ ] I read `AGENT_CONTRACT.md` and accept its limits.
- [ ] The token is read-only and stored as a secret.
- [ ] `out/audit.jsonl` is being kept.
- [ ] A named approver reviews every report before it is shared.
- [ ] `config/stakeholders.json` lists only the right people and is not committed.
- [ ] I ran the publish step as a dry run and read the emails before the first `--send`.
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
| `invalid stakeholder config` | bad address or audience in the config | fix the lines it lists |
| `ANTHROPIC_API_KEY is not set` | `--live` without a key | export the key or drop `--live` |

## 11. Status of this guide
| Step | Run for real? |
|---|---|
| Sections 3.1-3.4, 5 (synthetic dry run, tests, eval) | yes |
| Sections 3.5-3.8, 6 (live Jira connector) | **no - untested against a live site** |
| `--live` model run | **no - not run yet** |
| Section 7.3 (dry-run emails, refusal of drafts and edited files) | yes, run end to end on a clean checkout |
| Section 7.4 real sending | **simulated server in unit tests only; not tested against a real mail server** |
| Section 7.5 cron line and CI template | **no - untested** |
