# PM AI Toolkit

> AI agents, LLM evaluation, guardrails and human-in-the-loop governance for **program managers, project managers and PMOs** - with Jira integration, an audit log and a reproducible eval. Synthetic data only.

**Keywords:** AI for project management, agentic PMO, AI program manager, Jira AI agent, LLM evaluation, AI guardrails, AI governance, human-in-the-loop, status report automation, RAG status.

Ready-to-run AI building blocks for program and project managers. Every module comes with an evaluation, an agent
contract, a human approval gate and a step-by-step setup guide. It is built to show **how the AI works**, not just
that it exists: you can read the code, run it, break it, and measure it.

**Governance:** how the toolkit checks the AI, who must approve, what is enforced in code versus policy, and the known gaps are in [docs/AI_GOVERNANCE.md](docs/AI_GOVERNANCE.md).

**New here?** Read [docs/WHAT_IS_THIS.md](docs/WHAT_IS_THIS.md): what the project and this repository are, a worked example from the sample data, who it is best for, and what it does not do.

## What problem does it solve?

Writing the weekly status report from a ticket export is slow, and the two obvious shortcuts both fail. Ask a model
to do all of it and it miscounts, and it can cite tickets that do not exist. Use only rules and it cannot read a
comment such as "vendor access not available before April". This toolkit splits the work so each part is done by the
thing that is good at it.

## How it achieves it

```
ticket export -> code computes facts -> model (or rules) judges -> verifier checks -> DRAFT -> named human approves -> FINAL
                                                                                      every step logged to audit.jsonl
```

| Principle | What it means in practice |
|---|---|
| **Code counts, the model judges** | Counts, dates and lists are computed deterministically. The model never does arithmetic |
| **Verify before you trust** | Any answer that cites a ticket not in the data, or gives an invalid RAG, is rejected and replaced by the rule baseline, marked "(fallback)" |
| **Drafts, not decisions** | A report stays `STATUS: DRAFT` until a named person approves it. An empty name is refused |
| **Measure honestly** | Every number is tagged measured, modeled or hypothetical, with its limits stated |
| **Synthetic data only** | Nothing here comes from a real employer or customer |

Full explanation, design choices and limits: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## What you can do with it today

- Generate a weekly RAG status for six workstreams from a Jira-shaped export, with reasons that cite ticket keys.
- Run it with **no accounts and no API key** (offline baseline), or with a live model by adding `--live`.
- Approve a report as a named person and get an append-only audit trail with content fingerprints.
- **Run it on a schedule** (for example every weekday at 08:00): it pulls the data, drafts the report and emails only the approver.
- **Email and Slack the right people after approval:** a short exec view for sponsors, a full view for the delivery lead, a Slack post for the stakeholder channel, and a check-in to the owner of every Red or Amber workstream. It refuses to send anything unapproved or edited after approval, and sends nothing unless you pass `--send` (the default writes `.eml` and Slack `.json` files to inspect).
- **Chase an unapproved draft:** a reminder to the approver after 2 hours and an escalation (headline only, no report content) to a line manager after 4, each sent once.
- Score the agent against 24 labelled workstream-weeks and see a confusion matrix, the misses, and the grounding rate.
- Point it at your own Jira Cloud site through a read-only connector (not yet run against a live site, see status below).
- Reuse the agent contract and setup standard for any other AI helper your PMO introduces.

## Modules

| Module | Status |
|---|---|
| [01 Status & executive report agent](modules/m01_status_agent/README.md) | built, with scheduling and approval-gated email; offline baseline measured; live model, live Jira, a real mail server and a real scheduler **not yet run** |
| 02 Meeting-to-action pipeline | planned |
| 03 Risk & RAID intelligence | planned |
| 04 Backlog refinement assistant | planned |
| 05 Audit evidence & control mapping | planned |
| 06 AI vendor / model evaluation harness | planned |
| [07 Agentic PMO orchestrator](modules/m07_agentic_pmo/README.md) | scoped; delivery plan of 31 stories in 5 sprints is ready as a Jira import; **not built** |

New ideas go through [docs/IDEA_BACKLOG.md](docs/IDEA_BACKLOG.md). Each module follows the
[setup standard](docs/SETUP_STANDARD.md): what you get, prerequisites, numbered steps, credentials, a no-account dry
run, your-tool mapping, scheduling, governance checklist, verification, troubleshooting, and an honest status of
which steps were really run.

## Not technical? Start here

No coding needed: [docs/FOR_NON_TECHNICAL_USERS.md](docs/FOR_NON_TECHNICAL_USERS.md) explains the toolkit in plain words, how to try it in your browser with GitHub Codespaces (nothing to install), how to read the report, and a glossary.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/bharamprashant/pm-ai-toolkit)

## Quick start (about 5 minutes, no accounts)

```bash
git clone https://github.com/bharamprashant/pm-ai-toolkit
cd pm-ai-toolkit
python3 -m pip install pytest
python3 -m pytest -q                                   # expect: 51 passed
python3 -m modules.m01_status_agent.run --input data/synthetic/snapshots/2026-03-20.csv --as-of 2026-03-20
python3 -m modules.m01_status_agent.eval.run_eval      # expect: RAG accuracy 87.5%
```

Something went wrong? [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) has the full install guide, every
step's expected output, connecting your own Jira and a live model, and a table of the real errors you may hit
(wrong folder, missing `anthropic`, unset Jira variables, empty approver, externally-managed Python, cron
environment) with fixes.

## Results

Reproduced by `python3 -m modules.m01_status_agent.eval.run_eval` on 24 labelled workstream-snapshots.

| Measure | Value | Tag |
|---|---|---|
| Rule baseline RAG accuracy | 87.5% (21/24) | 🟢 measured |
| Baseline on comment-only cases | 0% (0/3) | 🟢 measured |
| Grounding rate (no invented keys) | 100% | 🟢 measured |
| Live model accuracy | not run yet | 🔴 hypothetical |
| Time saved per report | not measured | 🔴 hypothetical |

🟢 a script in this repo prints it, 🟡 modeled with a stated assumption, 🔴 designed but not tested.

**Read before trusting:** the data is synthetic and the labels are the author's design intent; 24 cases is small; two
scenario types are deliberately written so the signal sits in comments (a stress test the rule baseline is expected to
miss); the first run scored 66.7% because of a data-generator bug that was fixed and disclosed, with thresholds
untouched; the Jira connector and the live model have not been run for real. Details in
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#5-what-it-measured-and-what-that-does-and-does-not-prove).

## Repository map

```
core/          LLM interface (offline + Anthropic), audit log and approval, eval helpers
data/          synthetic Jira-shaped data generator (seeded, reproducible), snapshots, labels
modules/       one folder per module: code, README, SETUP.md, AGENT_CONTRACT.md, eval
governance/    reusable agent-contract template
docs/          getting started, how it works, setup standard, idea backlog
tests/         51 automated tests (run in CI on every push)
```

## Safety

Never commit a token (`.env`, `.env.*` and `*.token` are git-ignored). Use a read-only Jira token. Use synthetic data
or data you are explicitly allowed to use. Nothing here writes to Jira or marks a report final without a named human, and
stakeholder email is only sent for an approved, unchanged report when you pass `--send`.

MIT licensed. Author: Prashant Bharam.
