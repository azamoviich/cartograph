"""Layering violations via the Stable Dependencies Principle.

Purely graph-derived: instability I(cluster) = fan-out / (fan-in +
fan-out), from 0 (maximally stable — everything depends on it, it
depends on nothing) to 1 (maximally unstable). SDP says dependencies
should point from unstable towards stable clusters. A violation is a
stable cluster depending on a less-stable one — the "senior engineer"
finding in the risk map, and it needs no domain knowledge of the
intended architecture.
"""

from __future__ import annotations

import networkx as nx


def compute_instability(cluster_graph: nx.DiGraph) -> dict[str, float]:
    instability = {}
    for node in cluster_graph.nodes():
        fan_in = cluster_graph.in_degree(node)
        fan_out = cluster_graph.out_degree(node)
        total = fan_in + fan_out
        instability[node] = fan_out / total if total else 0.0
    return instability


def find_sdp_violations(cluster_graph: nx.DiGraph, min_margin: float = 0.1) -> list[dict]:
    instability = compute_instability(cluster_graph)
    violations = []
    for src, dst in cluster_graph.edges():
        margin = instability[dst] - instability[src]
        if margin > min_margin:
            violations.append(
                {
                    "src": src,
                    "dst": dst,
                    "src_instability": round(instability[src], 3),
                    "dst_instability": round(instability[dst], 3),
                    "margin": round(margin, 3),
                }
            )
    violations.sort(key=lambda v: v["margin"], reverse=True)
    return violations
