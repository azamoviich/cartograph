"""Circular-dependency detection, capped to stay tractable on real repos.

`nx.simple_cycles` is exponential and will hang on a hairball graph.
Instead: find strongly connected components first (cheap), and only
enumerate individual cycles within SCCs small enough to make that safe.
`TYPE_CHECKING`-guarded edges are excluded — otherwise every typed
modern codebase reports dozens of fake cycles from forward-reference
imports that never execute together.
"""

from __future__ import annotations

import networkx as nx

MAX_SCC_SIZE_FOR_ENUMERATION = 15
MAX_CYCLES_PER_SCC = 20


def _graph_excluding_type_checking(graph: nx.MultiDiGraph) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_nodes_from(graph.nodes())
    for src, dst, data in graph.edges(data=True):
        if not data.get("type_checking", False):
            g.add_edge(src, dst)
    return g


def find_cycles(graph: nx.MultiDiGraph) -> dict:
    g = _graph_excluding_type_checking(graph)
    sccs = [scc for scc in nx.strongly_connected_components(g) if len(scc) > 1]

    cycles: list[list[str]] = []
    truncated_sccs = 0
    for scc in sccs:
        if len(scc) > MAX_SCC_SIZE_FOR_ENUMERATION:
            truncated_sccs += 1
            continue
        subgraph = g.subgraph(scc)
        for i, cycle in enumerate(nx.simple_cycles(subgraph)):
            if i >= MAX_CYCLES_PER_SCC:
                break
            cycles.append(cycle)

    return {
        "scc_count": len(sccs),
        "scc_sizes": sorted((len(scc) for scc in sccs), reverse=True),
        "cycles": cycles,
        "truncated_sccs": truncated_sccs,
    }
