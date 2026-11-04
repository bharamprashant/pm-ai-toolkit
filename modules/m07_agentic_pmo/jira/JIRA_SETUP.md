# Manage the Agentic PMO build in Jira (step by step)

Follows the [setup standard](../../../docs/SETUP_STANDARD.md). Use a **personal** Jira Cloud site and keep
all Refyne or other employer data out of it.

**Status of this guide:** the CSV is generated and validated by `make_import.py` and `tests/test_m07_plan.py`.
The Jira import itself has **not been run against a live site**; field names in the importer can differ by site.

## 1. What you get
A ready plan: 8 epics, 31 stories, 101 story points, 5 sprints, 4 versions, components per agent, and
"blocks" links for every dependency. Points are the author's planning estimates, not measurements.

## 2. Steps
1. **Create a company-managed Scrum project** (key `AGPMO`). Choose company-managed, not team-managed: it supports components, versions and the link types this import uses.
2. **Add components** (Project settings -> Components): Orchestrator, Planner agent, Risk agent, Reporter agent, Governance reviewer, Eval harness, Docs & setup.
3. **Add versions** (Releases): v0.1, v0.2, v0.3, v1.0.
4. **Add an "Eval" status** (Project settings -> Workflows): `Backlog -> Ready -> In Progress -> In Review -> Eval -> Done`. Work that changes AI behaviour is not done until the eval was re-run and the result is in a comment.
5. **Import the CSV:** Jira settings -> System -> External system import -> CSV. Upload `agpmo_import.csv`, pick the AGPMO project, and map:
   - Issue Id -> Issue Id; Parent Id -> Epic link / Parent (the importer asks how to treat it).
   - Component/s, Fix Version/s, Priority, Labels (three columns) -> same names.
   - Story Points -> your site's story-point field (named "Story point estimate" or "Story Points").
   - Each "Outward issue link (Blocks)" column -> link type **Blocks**.
6. **Check the result:** open any story with dependencies and confirm "is blocked by" shows its prerequisites. Open a story from sprint 5 and confirm it is blocked by earlier work.
7. **Create five sprints** and drag stories by their `sprint-N` label (filter: `labels = sprint-1`).
8. **Dashboard:** add gadgets for sprint burndown, a filter `status = Eval`, and a filter of blocked issues (`issueFunction` is not needed; use `status != Done AND issueLinkType = "is blocked by"` if your site supports it, otherwise the board's flagged items).
9. **GitHub link:** install the GitHub for Jira app and put the issue key (for example `AGPMO-12`) in every branch name and PR title.
10. **Definition of Done** for each story: tests pass, eval result recorded, the setup step followed once, README numbers tagged measured/modeled/hypothetical, agent contract updated.

## 3. Use it as data for module 01
Export with module 01's read-only connector (`--jira-jql 'project = AGPMO'`) and run the status agent on it. The toolkit then reports on its own construction.

## 4. Changing the plan
Edit `PLAN` in `make_import.py`, run `python modules/m07_agentic_pmo/jira/make_import.py` (it refuses an invalid plan), then re-import into a fresh project or add only new rows.

## 5. Known limits
- Estimates and sprint assignment are one person's planning assumptions (modeled).
- CSV import cannot create the Eval status or sprints; steps 4 and 7 are manual.
- Rovo and paid features are not needed.
