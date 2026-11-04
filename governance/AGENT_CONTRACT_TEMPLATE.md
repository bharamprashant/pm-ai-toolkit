# Agent contract template (copy per agent)

| Item | Definition |
|---|---|
| Purpose | Draft a weekly RAG status per workstream from a ticket export |
| Owner | The program manager who runs it (named in the audit log at approval) |
| Inputs | Jira-shaped CSV or a read-only Jira API export |
| Allowed | Read exports; compute facts; propose RAG, a 2-sentence rationale and cited ticket keys; write a DRAFT file |
| Not allowed | Write to Jira or any system of record; send messages; change dates, owners or priorities; publish a report as final |
| Human decisions | Approving the report; accepting any RED; escalation and recovery plans |
| Stop conditions | Model output fails `verify()` (invalid RAG, empty rationale, ticket key not in the data) - the rule baseline is used instead and flagged "fallback" |
| Data handling | No credentials are sent to the model. Tokens live only in environment variables. Use synthetic or approved data only |
| Logging | Every draft, rejection and approval is appended to `audit.jsonl` with actor, time and a content fingerprint |
| Failure modes known | Cannot see anything outside the export; trusts comment text as written; small test set |
| Review cadence | Re-run the eval after any prompt, threshold or model change |
