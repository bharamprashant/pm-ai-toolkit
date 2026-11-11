# Setup guide - Meeting-to-action pipeline

## 1. What you get
A DRAFT list of actions from a meeting's notes: owner, task, due date, and the sentence each came from, with the
unclear ones flagged. Output: `out/actions_<date>_DRAFT.md`, and after a named person approves it, `..._FINAL.md`.

## 2. Prerequisites
| You need | Check with | Cost |
|---|---|---|
| Python 3.10 or newer | `python3 --version` | free |
| git | `git --version` | free |
| pytest | `python3 -m pip install pytest` | free |
| *(optional)* Anthropic API key | console.anthropic.com | pay per use; the eval is 8 calls per run |

## 3. Step-by-step setup
1. `git clone https://github.com/bharamprashant/pm-ai-toolkit && cd pm-ai-toolkit` then `python3 -m pip install pytest`. Stay in the repository root for every command.
2. `python3 -m pytest -q` should end with all tests passing.
3. `python3 data/synthetic/meetings.py` prints `wrote 8 meetings and labels for 29 actions`.

## 4. Credentials
Only the optional live model needs one: `export ANTHROPIC_API_KEY="..."` in your own terminal, never in a file in the repo. `.env` and `.env.*` are git-ignored. Delete the key in the console when you are done testing. Never paste it into a chat or screenshot it.

## 5. Dry run on synthetic data (no accounts)
```bash
python3 -m modules.m02_meeting_actions.run --notes data/synthetic/meetings/2026-03-02.txt
python3 -m modules.m02_meeting_actions.run --approve out/actions_2026-03-02_DRAFT.md --approver "Your Name"
python3 -m modules.m02_meeting_actions.eval.run_eval
```
Expected: a draft with one action for Priya due 2026-03-06; approval writes the FINAL file and logs it; the eval prints recall 31.0%.

## 6. Connect your own notes
Make a text file in the format in README.md. Use the exact names in the Attendees line as the people will be referred to in the notes (first names are fine, but they must match). Check with your organisation before using real notes with `--live`: the full text is sent to the model provider.

## 7. Schedule it
Not built. A fixed-time run does not fit this module, because a person has to supply the notes after each meeting. The natural trigger is a person running the command (or, later, a transcript tool saving the notes to a folder).

## 8. Governance checklist
- [ ] AGENT_CONTRACT.md read; data approved for the model provider if `--live`
- [ ] A named approver; the draft read, with the "Needs clarification" and "Rejected" sections checked
- [ ] `out/` and the audit log kept private
- [ ] Eval re-run after any prompt, date-rule or model change

## 9. Verify it worked
`python3 -m pytest -q` passes, and `run_eval` prints the numbers in README.md.

## 10. Troubleshooting
| What you see | Cause | Fix |
|---|---|---|
| `ValueError: meeting notes need a 'Date:' header line` | missing header line | add the three header lines and a blank line |
| An action you expected is under "Rejected" | the owner is not in Attendees, or the quote was altered | add the person to Attendees, or check the sentence |
| An action says `NEEDS DATE` | the deadline words cannot be turned into a date ("next sync", "soon") | set the date yourself; this is deliberate |
| Two meetings overwrote each other | same date, same `--out` folder | use a different `--out` |
| `RuntimeError: ANTHROPIC_API_KEY is not set` | `--live` without a key | export it in this terminal |

## 11. Status of this guide
| Step | Run for real? |
|---|---|
| Sections 3 and 5 (tests, dry run, approval, eval) | yes, on the repo as committed |
| `--live` model run | **yes - 11 Nov 2026, `run_eval --live --runs 3`: 100% recall, precision, all-correct, grounding on the synthetic set** |
| Real meeting notes | **no - synthetic data only** |
| Section 7 | not built |
