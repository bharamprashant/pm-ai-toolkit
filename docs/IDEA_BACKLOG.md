# Idea backlog

Every new idea lands here first, then gets a module number when it is scheduled.
Types: **automation** (fixed steps), **agent** (model chooses steps with tools), **multi-agent** (several roles), **governance** (policy, no code), **eval** (measurement).
Status: idea -> scoped -> building -> built (offline measured) -> live-tested.

| # | Idea | Type | Proves | Status |
|---|---|---|---|---|
| 01 | Status & executive report agent | agent | grounded judgment, verifier, approval gate | built (offline measured); live model and live Jira not run |
| 02 | Meeting-to-action pipeline | automation | extraction accuracy on labelled notes, code-resolved dates, owners checked against attendees | built (offline measured); live model not run |
| 03 | Risk & RAID intelligence | agent | reasoning over data, false-alarm rate | idea |
| 04 | Backlog refinement assistant | agent | human-review acceptance rate | idea |
| 05 | Audit evidence & control mapping | agent | retrieval with cited sources | idea |
| 06 | AI vendor / model evaluation harness | eval | model selection, guardrail metrics | idea |
| 07 | Agentic PMO orchestrator | multi-agent | dependency graph, agent contracts, audit log | scoped: Jira plan generated (31 stories, 5 sprints); not built |
| G1 | AI governance pack (policy, RACI, risk register, PMI AI standard and EU AI Act mapping) | governance | oversight design | idea |

## Rules for adding an idea
1. Name the real PM problem and who feels it.
2. State the baseline (what is done today, or what a simple rule would do).
3. State how it will be measured (a labelled test set, a metric, a known limit).
4. Check it is not a duplicate: merge it into an existing module if the pipeline is the same.
5. Use synthetic data only.
6. Plan a `SETUP.md` for it (see [SETUP_STANDARD.md](SETUP_STANDARD.md)). A module is not built until its setup steps have been followed once.
