# Agent contract template (copy per agent)

| Item | Definition |
|---|---|
| Purpose | Draft a weekly RAG status per workstream from a ticket export |
| Owner | The program manager who runs it (named in the audit log at approval) |
| Inputs | Jira-shaped CSV or a read-only Jira API export |
| Allowed | Read exports; compute facts; propose RAG, a 2-sentence rationale and cited ticket keys; write a DRAFT file; email the named approver that a draft is waiting; after approval, email the configured stakeholders and workstream owners (only with `--send`, and only if the approved file is unchanged) |
| Not allowed | Write to Jira or any system of record; email anyone before a named person has approved the report; email anyone not listed in the stakeholder config; change dates, owners or priorities; publish a report as final |
| Human decisions | Approving the report; deciding to send it (the publish command is run by a person); accepting any RED; escalation and recovery plans. The approver's name is self-declared, not authenticated; see docs/AI_GOVERNANCE.md |
| Stop conditions | Model output fails `verify()` (invalid RAG, empty rationale, ticket key not in the data) - the rule baseline is used instead and flagged "fallback" |
| Data handling | No credentials are sent to the model. With `--live`, workstream counts, ticket keys and open-item comment text are sent to the model provider (offline mode sends nothing). Tokens live only in environment variables. Use synthetic or approved data only |
| Logging | Every draft (including which workstreams the verifier rejected) and every approval is appended to `audit.jsonl` with actor, time and a content fingerprint. The log is not tamper-proof; see docs/AI_GOVERNANCE.md |
| Failure modes known | Cannot see anything outside the export; trusts comment text as written; small test set |
| Review cadence | Re-run the eval after any prompt, threshold or model change |
