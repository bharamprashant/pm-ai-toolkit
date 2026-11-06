# How it works, and why it is built this way

This document explains the problem, the design, how each design choice makes the output trustworthy, what you can
use it for, and where it stops being reliable. Numbers quoted here come from `eval/run_eval.py` and can be
reproduced with one command.

## 1. The problem

A program manager spends part of every week turning ticket exports into a status report. Two things make that
hard to automate with "just ask an AI":

1. **Models are unreliable at counting and dates.** Ask a model "how many items are overdue?" over a long ticket
   list and it will sometimes be wrong, and it will sound confident.
2. **Models can invent.** A status report that cites a ticket which does not exist, or a risk nobody raised, does
   more damage than no report.

The opposite approach, pure rules, is reliable but blind. A rule can count overdue items. It cannot read a comment
saying "vendor access not available before April" and decide a green-looking workstream is actually at risk.

## 2. The design in one sentence

**Code counts, the model judges, a verifier checks, a human approves, and everything is logged.**

```
Jira CSV or API
   |
   v
facts.py          deterministic: counts, dates, overdue, blocked, stale, comment text    (code)
   |
   v
model or rules    returns RAG + 2-sentence rationale + cited ticket keys                 (judgment)
   |
   v
verify()          rejects invalid RAG, empty rationale, or any ticket key not in the data (guardrail)
   |   reject -> falls back to the rule baseline and marks the row "(fallback)"
   v
DRAFT report      "STATUS: DRAFT - not approved"
   |
   v
human --approve   a named approver is required; refuses an empty name
   |
   v
FINAL report      every step appended to out/audit.jsonl with actor, time, content fingerprint
```

## 3. Each design choice and what it buys you

| Choice | Where in the code | What problem it solves |
|---|---|---|
| Facts are computed by code, never by the model | `facts.py` | The model cannot miscount or misread a date, because it is never asked to. It receives finished numbers |
| The model returns strict JSON | `core/llm.py` (`extract_json`; no temperature setting, so live runs can vary a little) | Output can be checked by a program instead of being read and hoped about |
| A verifier with a grounding rule | `agent.py` `verify()` | Any cited ticket key not present in the data rejects the whole answer. Invented evidence cannot reach a report |
| Rule baseline as the fallback | `agent.py` `baseline()` | If the model fails the verifier or is unavailable, you still get a safe, explainable answer, and it is marked |
| Swappable model interface | `core/llm.py` (`LLM` protocol, `OfflineBaseline`, `AnthropicLLM`) | The same pipeline runs offline for tests and with a live model in production. Other providers can be added without touching the agent |
| Draft then approval | `core/audit.py` `approve()` | A report is never final until a named person signs it. This is the human-in-the-loop control |
| Append-only audit log | `core/audit.py` | You can later answer "who approved this, when?" and, by comparing fingerprints, whether the draft changed. The log is append-only by design but is a plain file, not tamper-proof; see [AI_GOVERNANCE.md](AI_GOVERNANCE.md) |
| Labelled evaluation set | `data/synthetic`, `eval/run_eval.py`, `core/evalkit.py` | You get measured accuracy and a confusion matrix, so a prompt or model change can be judged on evidence, not feel |
| Evidence tags on every claim | README results table | Readers can tell a measured number from a modelled one from a hypothesis |
| Agent contract | `AGENT_CONTRACT.md` | States what the agent may and may not do, who owns it, and when it must stop. Maps to AI-governance expectations |

## 4. What it can do for you (usability)

- **Weekly status report in seconds.** One command turns a ticket export into a six-row workstream table with RAG,
  counts and cited tickets, ready for a person to review. Time saved per report has **not** been measured.
- **Evidence-linked reasons.** Each RAG has a reason and ticket keys, so a sponsor's "why is this amber?" is answered
  by pointing at specific tickets.
- **Risk hidden in comments.** With a live model, the agent can raise a workstream that looks green by dates but whose
  comments describe a blocker. The offline baseline cannot, and the eval shows exactly how much it misses (see below).
- **A governance template you can reuse.** `governance/AGENT_CONTRACT_TEMPLATE.md` and the approval and audit pattern
  apply to any AI helper a PMO introduces, not just this one.
- **A way to compare models.** Because the eval is a script, you can run the same 24 cases against a different prompt
  or model and see the difference in accuracy and false alarms.
- **A learning path.** Each module follows the same standard (`docs/SETUP_STANDARD.md`): what you get, prerequisites,
  numbered steps, credentials, a no-account dry run, your-tool mapping, scheduling, governance checklist,
  verification, troubleshooting, and an honest status of what has and has not been tested.

## 5. What it measured, and what that does and does not prove

Reproduce with `python3 -m modules.m01_status_agent.eval.run_eval`.

| Measure | Value | Tag |
|---|---|---|
| Rule baseline RAG accuracy on 24 labelled workstream-weeks | 87.5% (21/24) | measured |
| Baseline on the 3 comment-only cases | 0% (0/3) | measured |
| Grounding rate (no invented ticket keys) | 100% | measured |
| Live model accuracy | not run yet | hypothetical |
| Time saved per report | not measured | hypothetical |

Read these carefully:

- The data is **synthetic** and the labels are the author's design intent, not independent reviewers' judgments.
- 24 cases is small. One case is 4.2 percentage points.
- Two scenario types were written so the signal lives in comment text. That is a stress test of "does a model add
  value over rules?", not a typical week, so the baseline is expected to miss them.
- The first run scored 66.7%. The cause was a bug in the data generator, not in the rules: the "slipping" scenario
  gave its overdue item High priority, contradicting its own definition. The generator was fixed, the thresholds were
  untouched, and the run was repeated. The README states this openly.
- A test named `test_a_good_model...` uses a **simulated** model to prove the harness can show an improvement. It is a
  test of the harness, not a result about any real model.

What this proves: the pipeline works end to end, the guardrails trigger, and the harness can measure. What it does not
prove: that a live model beats the baseline on real programs. That needs Part D of `GETTING_STARTED.md` and a real,
approved dataset.

## 6. Adapting it

| You want to | Change |
|---|---|
| Use different thresholds (what counts as stale or red) | constants at the top of `facts.py`, then re-run the eval |
| Change the rules for RAG | `rule_rag()` in `facts.py` |
| Change what the model is told | `SYSTEM` in `agent.py`, then re-run the eval |
| Use another model provider | implement the small `LLM` protocol in `core/llm.py` |
| Map different Jira fields | `FIELDS` and `to_rows` in `jira_client.py`; mapping table in SETUP.md section 6 |
| Add your own labelled cases | extend `data/synthetic/generate.py` or add CSVs and labels in the same shape |
| Build a new module | copy the structure of `modules/m01_status_agent` and follow `docs/SETUP_STANDARD.md` |

## 7. Limits you should know before trusting it

- It sees only the export. It does not know about a conversation that never reached a ticket.
- It trusts comment text as written.
- The Jira connector and the live model path have **not** been run against real services yet.
- It is a decision aid. It does not replace the program manager's judgment, and a RED needs a human decision.
- Do not feed it confidential data unless your organisation has approved this use of an external model.

## 8. Roadmap

Seven modules are planned (`docs/IDEA_BACKLOG.md`). Module 01 is built. Module 07, an orchestrator where Planner,
Risk, Reporter and Governance-reviewer agents cooperate, is fully planned as a Jira project of 31 stories in five
sprints (`modules/m07_agentic_pmo/jira/`) but **not built**.
