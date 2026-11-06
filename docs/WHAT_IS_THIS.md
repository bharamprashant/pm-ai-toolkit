# What is this project, and what is it best used for?

Read this first if you want the whole picture in one place. It covers what the project is, what it does, what it
does not do, who benefits and how, a worked example from the real sample data, and where it is headed.

## 1. In one paragraph

**PM AI Toolkit is a public, open-source collection of AI helpers for program managers, project managers and PMOs.**
Each helper is a small, complete, tested program that does one recurring piece of PM work, shows you how it reached
its answer, checks itself before speaking, waits for a named human to approve, and keeps a record. Today one helper is
finished (a weekly status-report agent). The rest are planned and documented. The project is as much a **method for using AI
safely in project work** as it is software.

## 2. What is this GitHub repository?

GitHub is a website for storing and sharing project files and their history. This repository is the project's home:

| You will find | What it is for |
|---|---|
| `README.md` | the front page: summary, quick start, results |
| `docs/` | plain-language guides: this page, install guide, non-technical guide, how it works, idea backlog |
| `modules/` | the helpers. Each folder has the code, its own README, a step-by-step `SETUP.md`, an agent contract and its evaluation |
| `core/` | shared building blocks: the AI interface, the audit log, the scoring tools |
| `data/` | fictional ticket data used for demos and tests, with the "right answers" written in advance |
| `governance/` | a reusable template for defining what any AI helper may and may not do |
| `tests/` | automated checks that run on every change (CI), so a broken change shows a red mark |

Everything is free to read, copy and adapt under the MIT licence. Only fictional data is included.

## 3. What it does today (Module 01: status agent)

Input: a table of tickets (a Jira-style export). Output: a **draft weekly status report**, one row per workstream, with
a Red/Amber/Green colour, counts, and a short reason that names the tickets behind the colour.

What happens inside, in order:
1. **Facts, by code.** A program counts done, overdue, blocked and stale tickets. No AI is involved, so no miscounting.
2. **Judgment.** Simple rules, or an AI model if you connect one, choose the colour and write the reason.
3. **Check.** A verifier rejects the answer if the colour is invalid or it cites a ticket that is not in the data.
   A rejected answer is replaced by the rule version and flagged "(fallback)".
4. **Draft.** The report is stamped `STATUS: DRAFT - not approved`.
5. **Human approval.** A named person approves; an empty name is refused.
6. **Record.** Every draft and approval goes into an append-only log with a fingerprint of the content.

## 4. A worked example from the real sample data

The sample program is fictional ("Northwind Digital Onboarding"). Take the snapshot dated 2026-03-20.

**Payments** has no overdue, blocked or stale tickets, so the rules say **GREEN**. But ticket NW-113's last comment
reads: *"Vendor confirmed sandbox access will not be available before mid-April."* A person reading that would not call this
workstream green. Rules cannot read comments, so the offline baseline misses it. This is one of the three cases it gets wrong,
and it is wrong on purpose: it shows exactly where an AI model is supposed to add value.

**Collections** has one overdue ticket, so the rules say **AMBER** and cite NW-135. But NW-135's comment says it is a
*duplicate of NW-134 and is being cancelled with no impact*. A person would call it green. Here the rules raise a false alarm.

Those two cases are the point of the project. Counting is something code does perfectly. Reading a sentence and
deciding what it means is something a model can do. The toolkit lets each do its own job, then checks the model's answer
against the facts so it cannot make something up. Whether a real model actually gets these two right has **not been tested yet**;
the project is built so you can measure it the moment you connect one.

## 5. Who can use it, and for what

| You are | Best use | What you get |
|---|---|---|
| **A program or project manager** | Draft your weekly report faster, with ticket-level evidence | A reviewable first draft in seconds. Time saved is not yet measured |
| **A PMO lead** | Decide how your PMO will introduce AI helpers safely | A ready agent contract, approval gate, audit log and a setup standard to copy |
| **A manager or sponsor** | Understand why a workstream is Amber | Each colour comes with a reason that points at specific tickets |
| **Someone learning AI for PM work** | See a real, small, testable AI system end to end | Readable code, 51 tests, an evaluation, and honest notes on what failed first |
| **A team choosing an AI model or prompt** | Compare options on evidence | A repeatable eval with a confusion matrix, so a change can be judged, not felt |
| **An interviewer or recruiter** | See that the author built and understands the AI, not just used it | Working code, tests, disclosed bugs, documented limits |
| **A builder who wants to extend it** | Start a new PM helper on a proven pattern | The module structure and setup standard to follow |

## 6. What makes it different from "just ask an AI"

| Typical approach | This toolkit |
|---|---|
| Ask a chatbot to summarise tickets | Code computes the numbers first; the model only judges |
| Trust the answer | A verifier rejects answers citing tickets that do not exist |
| No record | Every step is logged with who, when, and a content fingerprint |
| "It seems good" | A scored eval on labelled cases, with a confusion matrix |
| Claims without proof | Each number is tagged measured, modeled or hypothetical |
| Final the moment it is generated | Draft until a named person approves |

## 7. What it does NOT do (so you are not surprised)

- It does **not** write to Jira, approve its own report, or email stakeholders on its own. A scheduled run stops at a draft and emails only the approver; a person approves and then runs the publish step.
- It does **not** replace your judgment. A RED still needs a human decision.
- It only sees what is in the export. A conversation that never reached a ticket is invisible to it.
- The Jira connector and the live-model path have **not** been run against real services yet.
- The results are on **synthetic** data with author-designed labels, 24 cases. They show the pipeline works, not
  how a model performs on your real program.
- Only module 01 is built. Modules 02 to 07 are planned.

## 8. What is planned

| Module | Idea | Status |
|---|---|---|
| 01 Status & executive report | weekly RAG report from tickets | built |
| 02 Meeting-to-action pipeline | turn meeting notes into owners, actions, dates | planned |
| 03 Risk & RAID intelligence | find and track risks, assumptions, issues, dependencies | planned |
| 04 Backlog refinement assistant | improve story quality and acceptance criteria | planned |
| 05 Audit evidence & control mapping | gather evidence and map controls for audits | planned |
| 06 AI vendor / model evaluation harness | compare models on your own cases | planned |
| 07 Agentic PMO orchestrator | Planner, Risk, Reporter and Governance agents working together | planned; delivery plan ready as a 31-story, 5-sprint Jira project |

Anyone can propose a new idea through the backlog (`docs/IDEA_BACKLOG.md`).

## 9. Where to go next

- **Just want to see it work, no coding:** [FOR_NON_TECHNICAL_USERS.md](FOR_NON_TECHNICAL_USERS.md)
- **Want to install and run it:** [GETTING_STARTED.md](GETTING_STARTED.md)
- **Want to know why it is built this way:** [HOW_IT_WORKS.md](HOW_IT_WORKS.md)
- **Want to propose or build a module:** [IDEA_BACKLOG.md](IDEA_BACKLOG.md) and [SETUP_STANDARD.md](SETUP_STANDARD.md)
