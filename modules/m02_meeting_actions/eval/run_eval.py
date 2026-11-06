"""Reproducible evaluation for module 02 (meeting-to-action).

  python -m modules.m02_meeting_actions.eval.run_eval              # offline baseline (no key needed)
  python -m modules.m02_meeting_actions.eval.run_eval --live       # also scores the live model
  python -m modules.m02_meeting_actions.eval.run_eval --live --runs 5

On 8 synthetic meetings with 29 hand-labelled actions it measures:
  * recall: share of the labelled actions that were found (matched by source sentence)
  * precision: share of reported actions that are real (decisions and status lines must not be reported)
  * owner and date correctness among the actions found; "all correct" = found with right owner AND due date
  * grounding: share of what the model proposed that passed the checker (quote in the notes, owner an attendee)
  * recall by archetype, because the rule baseline can only read "Action:" lines
Writes results.json next to this file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.evalkit import pct
from core.llm import AnthropicLLM
from modules.m02_meeting_actions import agent
from modules.m02_meeting_actions.facts import normalise, parse_meeting

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "synthetic"
ARCHETYPES = ["explicit", "implicit", "no_date", "no_owner"]
MAX_RUNS = 10


def _key(quote: str) -> str:
    return normalise(quote).removeprefix("action:").strip()


def _same(a: str, b: str) -> bool:
    a, b = _key(a), _key(b)
    return bool(a) and bool(b) and (a in b or b in a)


def evaluate(llm) -> dict:
    labels = json.loads((DATA / "meeting_labels.json").read_text())
    n_lab = matched = owner_ok = due_ok = all_ok = predicted = proposed = accepted = 0
    by_arch = {k: [0, 0] for k in ARCHETYPES}   # [found, total]
    missed, extra, wrong = [], [], []
    for mid, labelled in labels.items():
        meeting = parse_meeting((DATA / "meetings" / f"{mid}.txt").read_text())
        res = agent.assess(llm, meeting)
        proposed += res["proposed"]
        accepted += len(res["actions"])
        predicted += len(res["actions"])
        unused = list(res["actions"])
        for lab in labelled:
            n_lab += 1
            by_arch[lab["archetype"]][1] += 1
            hit = next((p for p in unused if _same(p["quote"], lab["quote"])), None)
            if hit is None:
                missed.append({"meeting": mid, "archetype": lab["archetype"], "quote": lab["quote"]})
                continue
            unused.remove(hit)
            matched += 1
            by_arch[lab["archetype"]][0] += 1
            o, d = hit["owner"] == lab["owner"], hit["due"] == lab["due"]
            owner_ok += o
            due_ok += d
            all_ok += o and d
            if not (o and d):
                wrong.append({"meeting": mid, "quote": lab["quote"], "owner": [hit["owner"], lab["owner"]],
                              "due": [hit["due"], lab["due"]]})
        extra += [{"meeting": mid, "quote": p["quote"]} for p in unused]
    return {
        "model": llm.name, "meetings": len(labels), "labelled_actions": n_lab, "reported": predicted,
        "recall": matched / n_lab, "precision": matched / predicted if predicted else 0.0,
        "owner_correct": owner_ok / matched if matched else 0.0, "due_correct": due_ok / matched if matched else 0.0,
        "all_correct": all_ok / n_lab, "grounding": accepted / proposed if proposed else 1.0,
        "recall_by_archetype": {k: v[0] / v[1] for k, v in by_arch.items()},
        "missed": missed, "false_positives": extra, "wrong_fields": wrong,
    }


def show(r: dict) -> None:
    print(f"\n== {r['model']} ==")
    print(f"meetings: {r['meetings']}   labelled actions: {r['labelled_actions']}   reported: {r['reported']}")
    print(f"recall: {pct(r['recall'])}   precision: {pct(r['precision'])}")
    print(f"owner correct (of found): {pct(r['owner_correct'])}   due date correct (of found): {pct(r['due_correct'])}")
    print(f"all correct end to end (of all labelled): {pct(r['all_correct'])}")
    print(f"grounding (proposed items that passed the checker): {pct(r['grounding'])}")
    print("recall by archetype: " + ", ".join(f"{k} {pct(v)}" for k, v in r["recall_by_archetype"].items()))
    for m in r["missed"]:
        print(f"  missed [{m['archetype']}] {m['meeting']}: {m['quote']}")
    for m in r["false_positives"]:
        print(f"  false positive {m['meeting']}: {m['quote']}")
    for m in r["wrong_fields"]:
        print(f"  wrong field {m['meeting']}: {m['quote']}  owner {m['owner']} due {m['due']}  (got, expected)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--runs", type=int, default=1, help=f"repeat the live run (1 to {MAX_RUNS})")
    a = ap.parse_args()
    if not 1 <= a.runs <= MAX_RUNS:
        ap.error(f"--runs must be between 1 and {MAX_RUNS}")
    out = [evaluate(agent.baseline())]
    show(out[0])
    if a.live:
        llm = AnthropicLLM()
        runs = [evaluate(llm) for _ in range(a.runs)]
        if a.runs == 1:
            show(runs[0])
        else:
            for i, r in enumerate(runs, 1):
                print(f"live run {i}/{a.runs}: recall {pct(r['recall'])}, precision {pct(r['precision'])}, all correct {pct(r['all_correct'])}")
            for k in ("recall", "precision", "all_correct", "grounding"):
                vals = [r[k] for r in runs]
                print(f"{k}: {pct(min(vals))} to {pct(max(vals))}, mean {pct(sum(vals) / len(vals))}")
        out += runs
    (Path(__file__).parent / "results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
