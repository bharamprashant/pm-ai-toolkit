"""Reproducible evaluation for module 01.

  python -m modules.m01_status_agent.eval.run_eval            # offline baseline (no key needed)
  python -m modules.m01_status_agent.eval.run_eval --live     # also scores the live model
  python -m modules.m01_status_agent.eval.run_eval --live --runs 5 --prompt both   # repeat runs, compare prompt v1 and v2

Measures, on the 24 labelled workstream-snapshots:
  * RAG accuracy and a confusion matrix
  * grounding rate: share of outputs that pass verify() (no invented ticket keys)
  * accuracy on the 'comment-only' archetypes (hidden_blocker, false_alarm), where the
    rule baseline cannot see the signal
Writes results.json next to this file.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from core.evalkit import accuracy, confusion, format_confusion, pct
from core.llm import AnthropicLLM
from modules.m01_status_agent import agent
from modules.m01_status_agent.facts import compute_facts, load_issues

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "synthetic"
COMMENT_ONLY = {"hidden_blocker", "false_alarm"}


def evaluate(llm, system: str = agent.SYSTEM) -> dict:
    labels = json.loads((DATA / "labels.json").read_text())
    pairs, comment_pairs, grounded, total = [], [], 0, 0
    misses = []
    for snap, per_ws in labels.items():
        facts = compute_facts(load_issues(DATA / "snapshots" / f"{snap}.csv"), date.fromisoformat(snap))
        for ws, lab in per_ws.items():
            res = agent.assess(llm, facts[ws], system)
            total += 1
            grounded += bool(res.get("verified"))
            pair = (res["rag"], lab["expected_rag"])
            pairs.append(pair)
            if lab["archetype"] in COMMENT_ONLY:
                comment_pairs.append(pair)
            if pair[0] != pair[1]:
                misses.append({"snapshot": snap, "workstream": ws, "archetype": lab["archetype"],
                               "predicted": pair[0], "expected": pair[1]})
    return {
        "model": llm.name, "cases": total, "accuracy": accuracy(pairs),
        "comment_only_cases": len(comment_pairs), "comment_only_accuracy": accuracy(comment_pairs),
        "grounding_rate": grounded / total, "misses": misses,
        "confusion": {k: dict(v) for k, v in confusion(pairs).items()},
    }


def show(r: dict) -> None:
    labels = ["GREEN", "AMBER", "RED"]
    print(f"\n== {r['model']} ==")
    print(f"cases: {r['cases']}")
    print(f"RAG accuracy: {pct(r['accuracy'])}")
    print(f"comment-only cases ({r['comment_only_cases']}): {pct(r['comment_only_accuracy'])}")
    print(f"grounding rate (no invented keys): {pct(r['grounding_rate'])}")
    from collections import Counter
    table = {k: Counter(v) for k, v in r["confusion"].items()}
    print(format_confusion({k: table.get(k, Counter()) for k in labels}, labels))
    for m in r["misses"]:
        print(f"  miss: {m['snapshot']} {m['workstream']} ({m['archetype']}) predicted {m['predicted']}, expected {m['expected']}")


MAX_RUNS = 10


def summarize(runs: list[dict]) -> dict:
    """Range across repeated runs, and how often each case was missed."""
    acc = [r["accuracy"] for r in runs]
    com = [r["comment_only_accuracy"] for r in runs]
    freq: dict[tuple, list[str]] = {}
    for r in runs:
        for m in r["misses"]:
            freq.setdefault((m["snapshot"], m["workstream"], m["archetype"], m["expected"]), []).append(m["predicted"])
    return {
        "runs": len(runs), "accuracy_each": acc, "accuracy_min": min(acc), "accuracy_max": max(acc),
        "accuracy_mean": sum(acc) / len(acc), "comment_only_each": com,
        "comment_only_mean": sum(com) / len(com), "grounding_min": min(r["grounding_rate"] for r in runs),
        "case_misses": [{"snapshot": k[0], "workstream": k[1], "archetype": k[2], "expected": k[3],
                         "missed_in_runs": len(v), "predicted": v} for k, v in sorted(freq.items(), key=lambda kv: -len(kv[1]))],
    }


def show_summary(name: str, s: dict) -> None:
    print(f"\n== {name}: {s['runs']} run(s) ==")
    print("accuracy per run: " + ", ".join(pct(x) for x in s["accuracy_each"]))
    print(f"accuracy range: {pct(s['accuracy_min'])} to {pct(s['accuracy_max'])}, mean {pct(s['accuracy_mean'])}")
    print(f"comment-only mean: {pct(s['comment_only_mean'])}   lowest grounding: {pct(s['grounding_min'])}")
    for m in s["case_misses"]:
        print(f"  {m['snapshot']} {m['workstream']} ({m['archetype']}, expected {m['expected']}): "
              f"missed in {m['missed_in_runs']}/{s['runs']} runs, predicted {', '.join(m['predicted'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--runs", type=int, default=1, help=f"repeat the live run (1 to {MAX_RUNS})")
    ap.add_argument("--prompt", choices=["v1", "v2", "both"], default="v1")
    a = ap.parse_args()
    if not 1 <= a.runs <= MAX_RUNS:
        ap.error(f"--runs must be between 1 and {MAX_RUNS}")
    base = evaluate(agent.baseline())
    out: list = [base]
    show(base)
    if a.live:
        llm = AnthropicLLM()
        for name in (["v1", "v2"] if a.prompt == "both" else [a.prompt]):
            runs = []
            for i in range(a.runs):
                r = evaluate(llm, agent.PROMPTS[name])
                r["prompt"], r["run"] = name, i + 1
                runs.append(r)
                if a.runs == 1:
                    show(r)
                else:
                    print(f"prompt {name} run {i + 1}/{a.runs}: accuracy {pct(r['accuracy'])}", flush=True)
            out += runs
            if a.runs > 1:
                show_summary(f"{llm.name} prompt {name}", summarize(runs))
    (Path(__file__).parent / "results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
