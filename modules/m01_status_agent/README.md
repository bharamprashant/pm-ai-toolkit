# Module 01 - Status & executive report agent

**Problem.** Program managers spend hours each week turning ticket exports into a status report. Counting
overdue items is easy; judging whether a workstream is really Red is not, because the risk is often written
in a comment ("vendor access not available before April"), not in a date field.

**Design.** Code computes the facts. The model only judges and explains. A verifier rejects anything not
grounded in the facts. A human approves before a report counts as final.

```
Jira CSV / API --> facts.py (counts, dates, lists) --> model or rule baseline
              --> verify() (no invented ticket keys, valid RAG) --> DRAFT report --> human --approve--> FINAL
                                                                    every step --> audit.jsonl
```

**Step-by-step automation setup:** see [SETUP.md](SETUP.md) (prerequisites, credentials, Jira field mapping, scheduling, governance checklist, troubleshooting and which steps are still untested).

## Run it (no key needed)
```bash
python data/synthetic/generate.py
python -m modules.m01_status_agent.run --input data/synthetic/snapshots/2026-03-20.csv --as-of 2026-03-20
python -m modules.m01_status_agent.run --approve out/status_2026-03-20_DRAFT.md --approver "Your Name"
python -m modules.m01_status_agent.eval.run_eval          # reproduces the numbers below
```
Live model: `pip install anthropic`, set `ANTHROPIC_API_KEY` (and optionally `PM_AI_MODEL`), add `--live`.
Your own Jira: set `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` as environment variables, then
`--jira-jql 'project = ABC' --export out/jira.csv` (read-only). Never commit a token.

## Results (24 labelled workstream-snapshots, reproduced by `eval/run_eval.py`)

| Measure | Value | Tag |
|---|---|---|
| Rule baseline RAG accuracy | 87.5% (21/24) | 🟢 measured |
| Baseline on comment-only cases | 0% (0/3) | 🟢 measured |
| Grounding rate (no invented keys) | 100% | 🟢 measured |
| Live model accuracy | not run yet | 🔴 hypothetical |
| Time saved per report | not measured | 🔴 hypothetical |

Tags: 🟢 a script in this repo prints it, 🟡 modeled with a stated assumption, 🔴 designed but not tested.

## Known limits (read these first)
- The data is synthetic and the labels are the author's design intent, not independent reviewers' judgments.
- n = 24 is small. One case is 4.2 percentage points.
- Two archetypes (hidden blocker, false alarm) were written so the signal sits in comment text. They test whether
  a model adds value over rules, so the baseline is expected to miss them. This is a stress test, not a typical week.
- **First-run disclosure:** the first run scored 66.7%. The cause was a data-generator bug (the "slipping" scenario
  gave its overdue item High priority, contradicting the archetype). I corrected the generator, not the rules, and
  re-ran. The rule thresholds are in `facts.py` and unchanged.
- `test_a_good_model...` uses a simulated model to prove the harness can show improvement. It is not a result.
- The Jira connector has not been run against a live site yet.

## Agent contract
See [AGENT_CONTRACT.md](AGENT_CONTRACT.md).
