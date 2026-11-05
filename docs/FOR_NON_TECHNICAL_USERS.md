# Using the toolkit without being technical

You do not need to know how to code. If you can follow a checklist, you can run this. This page explains
what it is in plain words, how to try it in your browser **without installing anything**, how to read what comes
out, and what to be careful about.

> **Honest status:** the browser route below (GitHub Codespaces) was opened and run by the author on 5 Nov 2026: the
> setup finished by itself, `python3 -m pytest -q` printed `49 passed`, and the status report ran on the sample data. It was
> tried once, on one account, so if a step does not match what you see, the
> [technical guide](GETTING_STARTED.md) is the other tested route (Linux, Python 3.13 and CI on 3.12).

## 1. What is this, in plain words?

Every week a program manager collects the state of many tasks (from Jira, a tool teams use to track work) and writes
a status report: which areas are on track (Green), at risk (Amber) or in trouble (Red). This toolkit does the first
draft of that report for you.

It works like a careful assistant:
1. A **calculator part** counts overdue, blocked and stale tasks. It never guesses.
2. A **judgment part** (simple rules, or an AI model if you connect one) decides the colour and writes a short
   reason that points at specific tasks.
3. A **checker** throws the answer away if it mentions a task that does not exist.
4. **You approve** it by name. Until then it says DRAFT and cannot be treated as final.
5. Everything is written to a **log**, so you can see who approved what and when.

The sample data is fictional ("Northwind Digital Onboarding"). Nothing real is used.

## 2. Try it in your browser (no installation)

You need a free GitHub account.
1. Open https://github.com/bharamprashant/pm-ai-toolkit
2. Click the green **Code** button -> **Codespaces** tab -> **Create codespace on main**.
3. Wait about a minute while it sets itself up. You will see a code editor in your browser. At the bottom is a
   **Terminal** panel. When setup ends it should print `49 passed`, which means everything works.
4. Click in the Terminal, paste this line, press Enter:
   `python -m modules.m01_status_agent.run --input data/synthetic/snapshots/2026-03-20.csv --as-of 2026-03-20`
5. A table appears: one row per workstream with its colour and a reason. A file is saved in the `out` folder.
6. To approve it, paste this (put your own name in the quotes):
   `python -m modules.m01_status_agent.run --approve out/status_2026-03-20_DRAFT.md --approver "Your Name"`
7. To see how good it is, paste: `python -m modules.m01_status_agent.eval.run_eval`
8. When finished, stop the codespace from the GitHub page so it does not keep running (free accounts have a monthly
   allowance).

Typing "python" lines is the only technical thing you do. Copy and paste them exactly.

## 3. How to read the report

| Column | Meaning |
|---|---|
| RAG | Green = on track, Amber = watch, Red = in trouble |
| Done | tasks finished out of total |
| Overdue | tasks past their due date and not finished |
| Blocked | tasks waiting on something else |
| Stale | tasks nobody has touched for over 7 days |
| Why | a short reason with task numbers (like NW-135) you can look up |

"(fallback)" next to a row means the AI's answer was rejected by the checker and simple rules were used instead. That
is the safety net working, not an error.

## 4. What the evaluation score means

The eval compares the toolkit's colours with 24 colours decided in advance. 87.5% means it matched 21 of 24. The three
misses are on purpose: they are cases where the real warning is hidden in a **comment** ("vendor access not available
before April"), which simple rules cannot read. That is where an AI model is meant to help. Whether a live model
really does better has **not been tested yet**.

## 5. Glossary

| Word | Plain meaning |
|---|---|
| RAG | Red / Amber / Green status colours |
| Workstream | one stream of related work inside a program |
| Jira | a popular tool teams use to track tasks |
| Ticket / issue | one task in Jira |
| Stale | not updated for a while |
| LLM / model | the AI that reads text and writes the reasoning |
| Guardrail | an automatic check that blocks bad output |
| Human-in-the-loop | a person must approve before it counts |
| Audit log | a permanent record of who did what and when |
| Baseline | the simple rule-based version used as a comparison and a safety net |
| Eval | a repeatable test that scores the tool against known answers |

## 6. Using it on your own work

Do not paste your company's real data into any tool or AI service unless your organisation has approved it. Ask first.
If approved, [GETTING_STARTED.md](GETTING_STARTED.md) Part D explains the read-only Jira connection; it needs someone
comfortable with settings and an API token, so ask your IT or a technical colleague to do that step with you.

## 7. If something goes wrong

Copy the error text and look it up in the [troubleshooting table](GETTING_STARTED.md#troubleshooting-real-errors-and-their-fixes).
The most common one: commands must run from the main project folder. In Codespaces the terminal already starts there.
