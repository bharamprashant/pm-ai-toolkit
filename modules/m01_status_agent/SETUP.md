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
3. **Run the tests.** `pip install pytest && python -m pytest -q` - expect `7 passed`.
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

## 7. Schedule it
Local weekly run (Monday 08:00): `0 8 * * 1  cd /path/to/pm-ai-toolkit && ./run_weekly.sh`
CI option: copy `automation/weekly-status.yml.example` to `.github/workflows/`, add the secrets in the repo settings, and keep the human approval step: the workflow produces a DRAFT artifact only; it never marks a report final.

## 8. Governance checklist
- [ ] I read `AGENT_CONTRACT.md` and accept its limits.
- [ ] The token is read-only and stored as a secret.
- [ ] `out/audit.jsonl` is being kept.
- [ ] A named approver reviews every report before it is shared.
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
| "(fallback)" in the report | the model cited a ticket not in the data, or an invalid RAG | read `audit.jsonl`; tighten the prompt; re-run the eval |
| `ANTHROPIC_API_KEY is not set` | `--live` without a key | export the key or drop `--live` |

## 11. Status of this guide
| Step | Run for real? |
|---|---|
| Sections 3.1-3.4, 5 (synthetic dry run, tests, eval) | yes |
| Sections 3.5-3.8, 6 (live Jira connector) | **no - untested against a live site** |
| `--live` model run | **no - not run yet** |
| Section 7 CI template | **no - untested** |
