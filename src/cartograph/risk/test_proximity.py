"""Test-proximity: an import-based proxy for "is this file tested."

Deliberately not coverage-based — public repos rarely commit coverage
data, and running a stranger's test suite to generate it is a security
problem. This only checks whether any file matching a test-file pattern
imports the module at all; it is approximate and labeled as such.
"""

from __future__ import annotations

import re

import networkx as nx

_TEST_PATH_PATTERN = re.compile(r"(^|/)(tests?)(/|$)|(^|/)test_[^/]+\.py$|_test\.py$")


def is_test_module(path: str) -> bool:
    return bool(_TEST_PATH_PATTERN.search(path.replace("\\", "/")))


def find_untested_hot_paths(graph: nx.MultiDiGraph, top_fraction: float = 0.1) -> list[dict]:
    test_modules = {n for n, d in graph.nodes(data=True) if is_test_module(d["path"])}
    non_test = [n for n in graph.nodes() if n not in test_modules]
    if not non_test:
        return []

    indegree = {n: graph.in_degree(n) for n in non_test}
    tested = {n for n in non_test if any(p in test_modules for p in graph.predecessors(n))}

    ranked = sorted(non_test, key=lambda n: indegree[n], reverse=True)
    cutoff = max(1, int(len(ranked) * top_fraction))

    return [
        {"module": n, "in_degree": indegree[n]}
        for n in ranked[:cutoff]
        if n not in tested and indegree[n] > 0
    ]
