"""Reproducible evaluation for module 01.

  python -m modules.m01_status_agent.eval.run_eval            # offline baseline (no key needed)
  python -m modules.m01_status_agent.eval.run_eval --live     # also scores the live model

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


def evaluate(llm) -> dict:
    labels = json.loads((DATA / "labels.json").read_text())
    pairs, comment_pairs, grounded, total = [], [], 0, 0
    misses = []
    for snap, per_ws in labels.items():
        facts = compute_facts(load_issues(DATA / "snapshots" / f"{snap}.csv"), date.fromisoformat(snap))
        for ws, lab in per_ws.items():
            res = agent.assess(llm, facts[ws])
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    results = [evaluate(agent.baseline())]
    if a.live:
        results.append(evaluate(AnthropicLLM()))
    for r in results:
        show(r)
    (Path(__file__).parent / "results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
