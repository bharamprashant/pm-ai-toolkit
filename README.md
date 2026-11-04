# PM AI Toolkit

> AI agents, LLM evaluation, guardrails and human-in-the-loop governance for **program managers, project managers and PMOs** - with Jira integration, an audit log and a reproducible eval. Synthetic data only.

**Keywords:** AI for project management, agentic PMO, AI program manager, Jira AI agent, LLM evaluation, AI guardrails, AI governance, human-in-the-loop, status report automation, RAG status.

Ready-to-run AI building blocks for program and project managers, each with an evaluation, an agent contract
and a human approval gate. Built to show how the AI works, not just that it exists.

| Module | Status |
|---|---|
| [01 Status & executive report agent](modules/m01_status_agent/README.md) | built, offline baseline measured, live model and live Jira not yet run |
| 02 Meeting-to-action pipeline | planned |
| 03 Risk & RAID intelligence | planned |
| 04 Backlog refinement assistant | planned |
| 05 Audit evidence & control mapping | planned |
| 06 AI vendor / model evaluation harness | planned |
| 07 Agentic PMO orchestrator | planned |

## Principles
1. **Code counts, the model judges.** Facts are computed deterministically; the model never does arithmetic.
2. **Verify before you trust.** Outputs that are not grounded in the data are rejected and flagged.
3. **Drafts, not decisions.** A named human approves; every step is logged.
4. **Measure honestly.** Each number is tagged measured, modeled or hypothetical, with known limits stated.
5. **Synthetic data only.** Nothing here comes from a real employer or customer.

## Quick start
```bash
pip install pytest        # anthropic is optional, only for --live
python data/synthetic/generate.py
python -m pytest -q
python -m modules.m01_status_agent.eval.run_eval
```
MIT licensed. Author: Prashant Bharam.
