# Agent contract - Meeting-to-action agent

| Item | Definition |
|---|---|
| Purpose | Draft a list of action items (owner, task, due date, source quote) from meeting notes |
| Owner | The program manager who runs it (named in the audit log at approval) |
| Inputs | A plain text notes file with a Meeting, Date and Attendees header |
| Allowed | Read the notes file; propose actions with a verbatim quote, an attendee as owner or none, and the words of any deadline; resolve those words to a date by fixed rules; write a DRAFT file; log it |
| Not allowed | Write a date itself; assign an owner who is not an attendee or guess one; send messages; create tickets, calendar entries or emails; mark anything final without a named person |
| Human decisions | Approving the action list; assigning owners and dates the draft flagged as missing; deciding what to do with rejected items. The approver's name is self-declared, not authenticated |
| Stop conditions | An item whose quote is not in the notes, whose owner is not an attendee, or whose due words are not in its quote is rejected and listed. A model answer that is not usable is replaced by the rule baseline and flagged |
| Data handling | Offline mode sends nothing anywhere. With `--live`, the attendee names, meeting date and the full notes text are sent to the model provider. Do not use real meeting notes without approval; notes often contain personal and confidential information. Keys live only in environment variables |
| Logging | Each draft (counts of accepted and rejected items, whether it fell back) and each approval is appended to `audit.jsonl` with actor, time and a content fingerprint. The log is not tamper-proof |
| Failure modes known | Misses commitments with no clear owner or phrased unusually; cannot read deadlines spread across sentences; cannot handle two owners on one action (it is rejected, not split); same-date meetings overwrite each other |
| Review cadence | Re-run the eval after any prompt, date-rule or model change |
