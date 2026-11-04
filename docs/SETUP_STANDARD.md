# Setup standard

Every module ships a `SETUP.md` that lets a program manager go from nothing to a running automation
without asking the author. A module is not "built" until its SETUP.md exists and its steps have been followed
once on a clean machine.

## Required sections (in this order)
1. **What you get** - the outcome in one sentence and the output file.
2. **Prerequisites** - accounts, tools, versions, cost. Say what is free.
3. **Step-by-step setup** - numbered, each step with the exact command or click path and the expected result.
4. **Credentials** - where each secret is created, where it is stored (environment variable or CI secret), and what must never be committed.
5. **Dry run on synthetic data** - the same pipeline with no accounts, so the reader can see it work first.
6. **Connect your own tool** - the field mapping and any tool-specific settings.
7. **Schedule it** - how to run it weekly (cron or CI), with the human approval step kept in the loop.
8. **Governance checklist** - agent contract read, permissions minimal, audit log on, approver named.
9. **Verify it worked** - what a correct run looks like and how to run the eval.
10. **Troubleshooting** - the failures seen so far and their fixes.
11. **Status of this guide** - which steps were run for real and which are untested. Never imply a step was tested if it was not.
