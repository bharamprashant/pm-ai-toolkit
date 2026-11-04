# Getting started: install, run, and fix what goes wrong

This guide takes you from nothing to a running, evaluated AI status agent. Allow about 10 minutes for the
no-account path (Part A to C) and about 30 minutes more to connect your own Jira and a live model (Part D).

**What was tested.** Parts A to C were run from a fresh `git clone` on Linux with Python 3.13, and the same
commands run in CI on Python 3.12 (see `.github/workflows/ci.yml`). The code is written for Python 3.10+ but
3.10 and 3.11 were not tested. macOS and Windows commands below are standard equivalents and were **not** run
by the author; they are marked. Parts D and E (live Jira, live model) have **not** been run yet. Every error
message quoted in the troubleshooting table was reproduced, except where marked.

---

## Part A. Prerequisites

| You need | Check with | Why | Cost |
|---|---|---|---|
| Python 3.10 or newer | `python3 --version` | everything is plain Python | free |
| git | `git --version` | to clone the repo | free |
| pip | `python3 -m pip --version` | to install pytest | free |
| A terminal | - | the agent runs from the command line | - |
| *(optional)* Jira Cloud site | - | to run on your own tickets (Part D) | free tier |
| *(optional)* Anthropic API key | - | to use a live model instead of the offline baseline | pay per use |

No database, no server, no Docker. The only third-party package for the core path is `pytest`, used for tests.

## Part B. Install

```bash
git clone https://github.com/bharamprashant/pm-ai-toolkit
cd pm-ai-toolkit
python3 -m pip install pytest
```

Windows PowerShell (untested by the author): use `py` or `python` instead of `python3`, same commands otherwise.
If you do not use git, use **Code -> Download ZIP** on GitHub, unzip, and open a terminal in that folder.

**Always run commands from the repository root** (the folder that contains `README.md`, `core/` and `modules/`).
The modules are imported as packages, so running from a sub-folder fails (see Troubleshooting 1).

## Part C. First run on synthetic data (no accounts, no keys)

Step 1. Regenerate the data. It is also committed, so this is optional, but it proves the generator is deterministic.
```bash
python3 data/synthetic/generate.py
```
Expected: `wrote 4 snapshots and labels for 24 cases`

Step 2. Run the tests.
```bash
python3 -m pytest -q
```
Expected: `10 passed`

Step 3. Produce a status report.
```bash
python3 -m modules.m01_status_agent.run --input data/synthetic/snapshots/2026-03-20.csv --as-of 2026-03-20
```
Expected: a table with six workstreams (KYC, Payments, Data-Sharing, Collections, Reporting, Compliance), each with a
RAG colour, counts of done, overdue, blocked and stale items, a one-line reason with ticket keys, and the last line
`draft saved to out/status_2026-03-20_DRAFT.md`. The header reads `STATUS: DRAFT - not approved`.

Step 4. Approve it as a named person (this is the human-in-the-loop step).
```bash
python3 -m modules.m01_status_agent.run --approve out/status_2026-03-20_DRAFT.md --approver "Your Name"
```
Expected: `approved -> out/status_2026-03-20_FINAL.md`. Open `out/audit.jsonl`: every draft and approval is logged with
who, when and a content fingerprint.

Step 5. Run the evaluation.
```bash
python3 -m modules.m01_status_agent.eval.run_eval
```
Expected (this is a real output from a clean clone):
```
cases: 24
RAG accuracy: 87.5%
comment-only cases (3): 0.0%
grounding rate (no invented keys): 100.0%
```
followed by a confusion matrix and the three cases the rule baseline gets wrong. Those three misses are intended:
the baseline cannot read comment text, which is exactly the gap a model is meant to close.

If you reached here, the install is good.

## Part D. Connect your own Jira (read-only) and a live model

This part is **not yet tested against a live site**. Follow it, and if a step fails, that is useful information.
Open an issue or tell the author. The full click-by-click version is in
[`modules/m01_status_agent/SETUP.md`](../modules/m01_status_agent/SETUP.md).

1. Use a Jira Cloud site you are allowed to use. Do not point this at an employer's Jira without permission.
2. Create an API token at id.atlassian.com -> Security -> Create and manage API tokens.
3. Set environment variables in **your own terminal** (never in a file in the repo):
   ```bash
   export JIRA_BASE_URL="https://your-site.atlassian.net"
   export JIRA_EMAIL="you@example.com"
   export JIRA_API_TOKEN="paste-here"
   ```
   Windows PowerShell (untested): `$env:JIRA_BASE_URL="https://your-site.atlassian.net"` and so on.
4. Make sure the issues have a **Component** (used as the workstream), due dates, and "Blocks" links. See the field
   mapping table in SETUP.md section 6, including how to find your site's Story Points field id.
5. Export read-only, then run the agent on the export:
   ```bash
   python3 -m modules.m01_status_agent.run --jira-jql 'project = ABC' --export out/jira.csv
   python3 -m modules.m01_status_agent.run --input out/jira.csv --as-of $(date +%F) --program "My Program"
   ```
6. Live model: `python3 -m pip install anthropic`, `export ANTHROPIC_API_KEY=...`, add `--live` to the run command.
   Optionally set `PM_AI_MODEL` to choose the model (default `claude-sonnet-5-5`).
7. Re-run the eval with the live model before trusting it. A model that has not been evaluated is a guess.

## Part E. Schedule it

Local weekly run, Monday 08:00: add `0 8 * * 1  JIRA_JQL='project = ABC' /path/to/pm-ai-toolkit/modules/m01_status_agent/run_weekly.sh`
to `crontab -e` (untested). Cron does not inherit your terminal's environment, so the Jira variables from Part D must
be provided inside the cron job or a wrapper script that only you can read; if they are missing you get the
`KeyError` from Troubleshooting 3. Or copy `modules/m01_status_agent/automation/weekly-status.yml.example` into `.github/workflows/`
and add secrets in the repo settings. Either way the schedule produces a **DRAFT only**. A person approves it.

---

## Troubleshooting (real errors and their fixes)

| # | What you see | Cause | Fix |
|---|---|---|---|
| 1 | `No module named 'modules'` (reproduced) | You ran the command from inside a sub-folder | `cd` to the repository root, the folder with `README.md`, then run again |
| 2 | `RuntimeError: pip install anthropic to use the live model` (reproduced) | You used `--live` without the SDK | `python3 -m pip install anthropic`, or drop `--live` to use the offline baseline |
| 3 | `KeyError: 'JIRA_BASE_URL'` or `'JIRA_EMAIL'` (reproduced) | Jira environment variables are not set in **this** terminal | Export them again. Variables do not carry over to a new terminal window |
| 4 | `ValueError: approval requires a named approver` (reproduced) | `--approve` without `--approver` | Add `--approver "Your Name"`. This is deliberate: nothing becomes final without a named person |
| 5 | `python3: command not found` or Python 3.8/3.9 | Old or missing Python, or Windows where the command is `python`/`py` | Install Python 3.10+ from python.org, or try `py` or `python` instead of `python3` |
| 6 | `error: externally-managed-environment` when running pip (Python behaviour on many Linux and Homebrew setups; not reproduced here) | The OS protects its system Python | Use a virtual environment: `python3 -m venv .venv && source .venv/bin/activate`, then `pip install pytest`. As a last resort `pip install --break-system-packages pytest` |
| 7 | `pytest: command not found` | pytest not installed, or pip installed it for a different Python | Use `python3 -m pytest` and `python3 -m pip install pytest` so both use the same Python |
| 8 | `git clone` asks for a password or fails with permission denied | The URL was typed wrongly, or an SSH URL was used without a key | Use the HTTPS URL exactly as shown in Part B; the repo is public and needs no login |
| 9 | pip or git hang or time out | Corporate proxy or firewall | Set `HTTPS_PROXY` as your IT team instructs, or install on a personal machine |
| 10 | HTTP 401 or 403 from Jira (not yet tested live) | Wrong email, expired token, or no permission on the project | Recreate the token, check the account can browse the project |
| 11 | Every workstream shows "Unassigned" (not yet tested live) | Issues have no Components | Add components, one per workstream, or change the mapping in `jira_client.py` |
| 12 | Story points all show 0 (not yet tested live) | Your site uses a different custom field id | Find it at `https://<site>/rest/api/3/field` and edit `FIELDS` and `to_rows` in `jira_client.py` |
| 13 | A report row ends with "(fallback)" | The model cited a ticket that is not in the data, or returned an invalid RAG, so the verifier rejected it and used the rule baseline | This is the safety net working. Read `out/audit.jsonl` for the reason, tighten the prompt, re-run the eval |
| 14 | Eval accuracy differs from 87.5% | You changed a threshold in `facts.py`, the prompt, or the data | Expected. The 87.5% belongs to the committed thresholds and data |
| 15 | `out/` files do not appear in git | `out/` is in `.gitignore` on purpose | Reports and the audit log stay local. Do not commit data from a real program |

## Safety rules while setting up

- Use synthetic data or data you are explicitly allowed to use. The repo ships only fictional data.
- Never commit a token. `.env`, `.env.*` and `*.token` are already in `.gitignore`, but check `git status` before every commit.
- Use a Jira token from an account with **read-only** access. The connector only sends GET requests.
- Nothing in this repo writes to Jira, sends messages, or publishes a report as final.
