"""Tiny evaluation helpers shared by all modules.

Every number a module publishes in its README must come from a function here
being called by an eval script, so readers can reproduce it.
"""
from __future__ import annotations

from collections import Counter, defaultdict


def accuracy(pairs: list[tuple[str, str]]) -> float:
    """pairs = [(predicted, expected), ...]"""
    return sum(p == e for p, e in pairs) / len(pairs) if pairs else 0.0


def confusion(pairs: list[tuple[str, str]]) -> dict[str, Counter]:
    """expected -> Counter(predicted)"""
    table: dict[str, Counter] = defaultdict(Counter)
    for pred, exp in pairs:
        table[exp][pred] += 1
    return table


def format_confusion(table: dict[str, Counter], labels: list[str]) -> str:
    head = "expected \\ predicted".ljust(22) + "".join(l.rjust(8) for l in labels)
    rows = [head]
    for exp in labels:
        rows.append(exp.ljust(22) + "".join(str(table[exp][p]).rjust(8) for p in labels))
    return "\n".join(rows)


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"
