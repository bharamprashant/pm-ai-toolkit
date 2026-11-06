# AI governance: how the toolkit checks itself, who must approve, and where the controls stop

This page describes the governance controls **as they exist in the code today**, how strong each one is, and what
is still missing. It was written after re-reading the source, and it deliberately separates three strengths:

- **ENFORCED IN CODE**: the program refuses or rejects. You cannot skip it by accident.
- **BY DESIGN**: the structure of the program makes it the normal path, but a person with file access could bypass it.
- **POLICY ONLY**: written down, but nothing in the code stops you from ignoring it.

This is an engineering description, not legal advice, and not a compliance claim. It has not been assessed against
any regulation or standard.

## 1. The controls at a glance

| # | Control | What it does | Strength | Where |
|---|---|---|---|---|
| 1 | Facts computed by code | The model is given finished counts, dates and lists, never raw arithmetic | ENFORCED IN CODE | `facts.py` |
| 2 | Grounding check | Rejects a model answer with an invalid colour, an empty reason, or a cited ticket that is not in the data | ENFORCED IN CODE | `agent.py` `verify()` |
| 3 | Safe fallback | A rejected answer is replaced by the rule baseline and flagged "(fallback)"; the model's text is never used | ENFORCED IN CODE | `agent.py` `assess()` |
| 4 | Draft status | Every report starts as `STATUS: DRAFT - not approved` | ENFORCED IN CODE | `agent.py` `render()` |
| 5 | Named approver | Approval fails with an empty or blank name; the final file is stamped with the approver and UTC time | ENFORCED IN CODE (name only, see 3.2) | `core/audit.py` `approve()` |
| 6 | Audit log | Draft creation and approval are written as one JSON line each, with actor, UTC time and a content fingerprint | BY DESIGN (see 4.2) | `core/audit.py` |
| 7 | Read-only Jira access | The connector only issues GET requests and never writes to Jira | ENFORCED IN CODE (the token's real permissions are yours to limit) | `jira_client.py` |
| 8 | No auto-publish | The agent never writes to a system of record and never approves its own report. A scheduled run stops at a draft and only emails the approver | ENFORCED IN CODE | whole module |
| 8a | Approval-gated email | `notify publish` refuses a report that is a draft, has no approval record in the log, or was edited after approval (fingerprint check). Nothing is sent without `--send`; the default writes `.eml` files for inspection | ENFORCED IN CODE | `notify.py`, `core/audit.py` `verify_approved()` |
| 8b | Recipient allow-list | Email goes only to addresses in `config/stakeholders.json`, which is validated (bad addresses and header-injection attempts are rejected) and git-ignored | ENFORCED IN CODE | `notify.py` `load_config()` |
| 8d | Slack safety | Webhook URLs only from environment and only `https://hooks.slack.com/services/...`; the URL is never logged; the draft goes only to a separate review webhook and never falls back to the stakeholder channel; text from tickets is escaped so it cannot @mention or link | ENFORCED IN CODE | `slack_notify.py` |
| 8e | Reminder and escalation | A draft left unapproved is chased by `notify remind`: the approver after 2 hours, an escalation contact after 4. The escalation message carries the headline only, never the report, and each level is sent once | ENFORCED IN CODE (the timing is a schedule you set up) | `notify.py` `due_reminders()` |
| 8c | Credentials only in environment | SMTP settings come from environment variables; unencrypted sending is refused; error text is never logged | ENFORCED IN CODE | `notify.py` |
| 9 | Agent contract | Purpose, owner, allowed and forbidden actions, human decisions, stop conditions, review cadence | POLICY ONLY | `AGENT_CONTRACT.md` |
| 10 | Evaluation before trust | A scored test on labelled cases, to be re-run after any prompt, threshold or model change | BY DESIGN (re-running is up to you) | `eval/run_eval.py` |
| 11 | Evidence tags | Every published number is tagged measured, modeled or hypothetical | POLICY ONLY | README |

## 2. How it checks the AI before anyone sees the answer

The model is never trusted by default. Three layers sit between it and your report:

1. **The model is not asked to count.** Code computes done, overdue, blocked, stale and the open-item comments. The
   model only decides the colour and writes a short reason.
2. **The verifier.** For each workstream it checks: the colour is one of GREEN, AMBER, RED; the reason is not empty; and
   every ticket key the model cites exists in that workstream's data (overdue, blocked, stale or commented tickets).
   One failure rejects the whole answer for that workstream.
3. **The fallback.** A rejected answer is discarded. The deterministic rule version is used instead, the row is marked
   "(fallback)", and the reason for the rejection is appended to that row's text. The draft's log entry lists which
   workstreams were rejected. In the offline mode the report is built entirely by the rules.

**What the verifier cannot catch.** It proves a citation is *real*, not that the reasoning is *right*. A model can cite
an existing ticket and still draw the wrong conclusion, or leave out the ticket that mattered. That is why the report is a
draft, why a human reads it, and why the evaluation exists. Live-model accuracy has not been measured yet.

## 3. Authority: who confirms a decision, and how

### 3.1 What the code enforces
1. The agent can only produce a **draft**. There is no code path in which the agent marks its own output final.
2. Turning a draft into a final report requires someone to run the approve command with an approver name.
   An empty or blank name raises an error and nothing is written.
3. The final file is stamped `STATUS: APPROVED by <name> at <UTC time>`, and the log records the approver, the time, the
   draft and final file names, and a fingerprint (SHA-256, first 12 characters) of the draft that was approved.
4. The report ends with a **Decisions needed** section. Every workstream rated RED is listed with "confirm recovery plan
   or descope", so the people who must decide see what is waiting for them.

### 3.2 What the code does NOT enforce (read this before relying on the approval)
- **The approver name is self-declared.** The tool does not log anyone in, does not check a role, and does not verify
  that the name is real. Anyone who can run the command can type any name.
- **No separation of duties.** The person who generates the draft can approve it. There is no two-person rule.
- **No per-decision sign-off.** One approval covers the whole report. The agent contract says accepting a RED is a human
  decision, but the code does not make the approver individually accept each RED.
- **No automatic check that the draft is unchanged.** The log stores the fingerprint at creation and again at approval,
  but nothing compares them for you. If someone edits the draft in between, the fingerprints will differ, and only a
  person comparing the two log lines would notice.
- **Approved files can be edited afterwards, but this is now detected before any email.** The log stores a fingerprint of the approved file (`final_sha`), and `publish` refuses a file that no longer matches. Someone who can edit both the file and the log could still defeat this.

### 3.3 How to get real authority control in practice (recommended, not built)
| Gap | Practical way to close it today |
|---|---|
| Name is self-declared | Run the agent inside a system with real logins: for example commit each draft to a repository and require approval through a pull-request review by a named reviewer; or restrict the folder and the command to the report owner |
| No separation of duties | Require that the approver is a different person from the one who ran the draft |
| No per-RED acceptance | Have the approver record each RED decision as a comment on the review, or extend the code to ask per RED |
| Draft edited before approval | Compare `sha` in the `draft_created` log line with `draft_sha` in the `approved` line |
| Final edited afterwards | Detected automatically before email (fingerprint). Still keep finals in write-protected or versioned storage |

## 4. The audit trail

### 4.1 What is recorded
| Event | Written when | Fields |
|---|---|---|
| `draft_created` | a report is generated | time (UTC), actor (`agent:offline-baseline` or `agent:anthropic:<model>`), draft file, fingerprint, list of workstreams the verifier rejected |
| `approved` | a draft is approved | time (UTC), approver name, draft file, final file, fingerprint of the approved draft and of the final file |
| `jira_export_readonly` | a Jira export is made | time (UTC), actor `system`, output file |
| `email_prepared` | a dry run writes an `.eml` file | time (UTC), kind, recipient, subject, report file and fingerprint |
| `email_sent` | an email is really sent | same fields as above |
| `email_failed` | a send fails | time (UTC), kind, recipient, error class only (never the error text) |
| `email_sent` / `slack_sent` with kind `reminder_1`, `reminder_2`, `slack_reminder`, `slack_escalation` | a reminder or escalation is really sent | same fields; this is what stops a level repeating |
| `slack_prepared` / `slack_sent` / `slack_failed` | a Slack payload is written, posted, or fails | time (UTC), kind, report file and fingerprint (error class only on failure; never the webhook URL) |

### 4.2 What is not recorded, and how strong the log is
- **Not recorded:** the prompt text or version, the input data fingerprint, the rejection reason (it is in the report row,
  not the log), and who edited a draft.
- **Not tamper-proof.** The log is a plain text file that the program only appends to. It is not signed and not
  hash-chained, so a person with file access could edit or delete lines. Treat it as a useful record, not as evidence that
  would survive an adversary. For stronger assurance, ship the log to write-once storage.
- The fingerprint only helps if someone compares it. See 3.2.

## 5. Data handling

| Mode | What leaves your machine |
|---|---|
| Offline (default) | **Nothing.** The rule baseline runs locally |
| `--live` | The workstream name, counts, ticket keys, due and stale lists, and the **text of open-item comments** go to the Anthropic API |
| Email (`--send`) | The report text and recipient addresses go to **your** mail server (SMTP) using your own credentials |
| Slack (`--send`) | The report text goes to Slack (a third party) through your webhook; every member of the channel can read it |
| `--live`, never sent | your Jira token and email, ticket summaries and assignee names (the code does not include them in the model request) |
| Jira export | Read-only GET requests to your own Jira site |

Comment text is free text. People sometimes put names, customer details or confidential commercial information in
comments. Before using `--live` on real data, get your organisation's approval for sending that text to an external model
provider, and check what your comments contain. The repository ships fictional data only.

## 6. Human decisions the tool never takes

From the agent contract: approving a report, accepting a RED, and agreeing escalation and recovery plans. The tool also
never changes dates, owners or priorities, and never writes to Jira or any system of record. It does send email and Slack messages, but only (a) a review request to the named approver, and (b) after a person has approved and run the publish command with `--send`, the approved report to the configured stakeholders (email and the stakeholder Slack channel) and a check-in to each RED or AMBER workstream owner (email, and an @mention in Slack).

## 7. Known risks and how each is handled

| Risk | Handled by | Residual risk |
|---|---|---|
| Model invents a ticket or evidence | Grounding check and fallback | None for invented keys; reasoning can still be wrong |
| Model miscounts or misreads dates | It is never given that job | None for counts; thresholds are rules you choose |
| Model misses a hidden blocker | Human review of the draft; the evaluation exposes the miss rate | Live-model miss rate unknown |
| Model over-alarms (false RED) | Human review; the eval's confusion matrix | Live-model false-alarm rate unknown |
| Approver is away and the report is never published | `remind` nudges the approver, then tells an escalation contact (headline only) | Needs the reminder job running on a persistent machine; the contact cannot approve on their behalf |
| Someone approves without reading | Draft status and the Decisions section make the ask visible | Cannot be prevented by software; needs a review habit |
| Someone approves under another person's name | Not prevented by the tool | Needs login-based approval, see 3.3 |
| A wrong or unapproved report reaches stakeholders | `publish` refuses drafts and edited files; the dry run lets a person read the exact emails first; `--send` is explicit | A person can still approve a wrong report and run `--send` |
| Report posted to the wrong Slack channel | A webhook is bound to one channel when you create it; the draft uses a separate private webhook and never the stakeholder one | Choosing the right channel in Slack when creating the webhook; anyone in the channel can read and copy the report |
| Ticket text pings the whole workspace (`<!channel>`) | Slack escaping of all ticket and model text | Owners' @mentions are intended and come only from the config file |
| Webhook URL leaks | Environment only; never logged; revoke and replace in Slack | Anyone holding the URL can post to that channel until revoked |
| Email goes to the wrong person | Recipients come only from the validated config file | A mistake in the config file itself; review it before first use |
| Recipient addresses (personal data) sit in files | Config and `out/` are git-ignored; the log stores recipient addresses | Protect the folder; do not commit it; delete the log per your retention rules |
| Check-in emails sound like instructions from the AI | Sent in the approver's name as Reply-To; each says it comes from an approved report | Tone and need for a check-in are still the approver's call |
| Log edited after the fact | Not prevented by the tool | Needs write-once storage |
| Confidential comments sent to a provider | `--live` is opt-in; offline mode is the default | Your approval and data checks |
| Prompt or threshold changed and quality drops | Re-run the eval after every change | Relies on discipline; not automated |
| Over-trust in a well-formatted report | Evidence tags, stated limits, "(fallback)" flag | Human factor |

## 8. Informal alignment with common AI-governance principles

This is a plain-language mapping for orientation. It is **not** an assessment against any regulation or standard.

| Principle widely used in AI governance | How the toolkit relates to it | Gap |
|---|---|---|
| Human oversight | Drafts only; a named approver; decisions listed | Approver identity not authenticated |
| Transparency | Reasons cite tickets; the report states what is code and what is model; fallback is flagged | Prompt not logged |
| Accountability | An owner and approver are named in the contract and log | Roles not enforced |
| Accuracy and robustness | Verifier, fallback, labelled evaluation | Only synthetic data; live model run once (tied the rules, under-called two RED weeks) |
| Record-keeping | Append-only style log with fingerprints | Not tamper-proof |
| Data protection | Offline default; read-only access; credentials never sent to the model | Comment text goes to the model in live mode |

Mapping the controls to the PMI AI standard and the EU AI Act in detail is a planned task (see the Jira plan for module 07),
**not done yet**.

## 9. Checklist before using it on real work

- [ ] I read the agent contract and accept its limits.
- [ ] My organisation approves using this tool on this data, and approves sending comment text to an external model (or I use offline mode).
- [ ] The Jira token belongs to an account with read-only access.
- [ ] Someone other than the person who generated the draft will approve it, and I have a way to know who they are.
- [ ] I run the evaluation before the first real use and after any change to the prompt, thresholds or model.
- [ ] I compare the draft and approval fingerprints, or my process makes that unnecessary.
- [ ] I ran `notify publish` as a dry run and read the emails before the first `--send`.
- [ ] The Slack review webhook points to a private channel, and I know who can read the stakeholder channel.
- [ ] `config/stakeholders.json` lists only people who should receive this report, and the folder is access-controlled.
- [ ] The audit log is kept somewhere it cannot be quietly edited.
- [ ] Every RED has a named human decision attached.

## 10. Governance improvements planned

None of these exist yet: hash-chained audit log; approver identity through pull-request review; per-RED acceptance;
automatic draft-versus-approval fingerprint check; logging the prompt version, input fingerprint and rejection reasons;
a written mapping to the PMI AI standard and the EU AI Act. Module 07 (the multi-agent orchestrator) adds a reviewer agent
and a permission check on which tools each agent may call.
