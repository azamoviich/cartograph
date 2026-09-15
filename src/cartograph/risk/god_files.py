"""God-file detection: rank-relative, never an absolute threshold.

Absolute thresholds (e.g. "flag files over 500 lines") break across
repos of wildly different sizes. Everything here is a percentile rank
within the one repo being analyzed.
"""

from __future__ import annotations

import networkx as nx


def _percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda kv: kv[1])
    n = len(ordered)
    ranks: dict[str, float] = {}
    for i, (key, _) in enumerate(ordered):
        ranks[key] = i / (n - 1) if n > 1 else 1.0
    return ranks


def find_god_files(graph: nx.MultiDiGraph, top_fraction: float = 0.1) -> list[dict]:
    indegree = dict(graph.in_degree())
    loc = {n: d["loc"] for n, d in graph.nodes(data=True)}
    symbol_count = {n: len(d["symbols"]) for n, d in graph.nodes(data=True)}

    r_indegree = _percentile_ranks(indegree)
    r_loc = _percentile_ranks(loc)
    r_symbols = _percentile_ranks(symbol_count)

    composite = {
        n: (r_indegree.get(n, 0) + r_loc.get(n, 0) + r_symbols.get(n, 0)) / 3
        for n in graph.nodes()
    }

    ranked = sorted(composite.items(), key=lambda kv: kv[1], reverse=True)
    cutoff = max(1, int(len(ranked) * top_fraction))

    return [
        {
            "module": module,
            "score": round(score, 4),
            "in_degree": indegree[module],
            "loc": loc[module],
            "symbol_count": symbol_count[module],
        }
        for module, score in ranked[:cutoff]
        if score > 0
    ]
