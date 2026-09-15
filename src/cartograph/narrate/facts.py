"""Assemble the grounded facts that go into each prompt.

The LLM never sees the graph's conclusions as open questions — every
fact here is computed, not asked for. Cluster prompts get file lists,
one-liners, and named neighbor clusters; they never get source code.
"""

from __future__ import annotations

import networkx as nx


def select_l0_candidates(graph: nx.MultiDiGraph, max_candidates: int = 80) -> list[str]:
    """High-centrality files with no docstring — the only files worth an LLM call at L0."""
    candidates = [
        n
        for n, d in graph.nodes(data=True)
        if not d.get("docstring") and graph.in_degree(n) > 0
    ]
    candidates.sort(key=lambda n: graph.in_degree(n), reverse=True)
    return candidates[:max_candidates]


def _one_liner_for(graph: nx.MultiDiGraph, module: str, l0_notes: dict[str, str]) -> str:
    docstring = graph.nodes[module].get("docstring")
    if docstring:
        return docstring.splitlines()[0][:200]
    if module in l0_notes:
        return l0_notes[module]
    symbols = graph.nodes[module].get("symbols") or []
    return f"defines {', '.join(symbols[:4])}" if symbols else "(no docstring, no top-level symbols)"


def build_cluster_facts(
    cluster: str,
    graph: nx.MultiDiGraph,
    assignment: dict[str, str],
    cluster_graph: nx.DiGraph,
    l0_notes: dict[str, str],
    max_files_listed: int = 15,
) -> dict:
    members = [m for m, c in assignment.items() if c == cluster]
    members_by_indegree = sorted(members, key=lambda m: graph.in_degree(m), reverse=True)

    external_deps: set[str] = set()
    for m in members:
        external_deps.update(graph.nodes[m].get("external_deps", []))

    inbound = [
        {"cluster": src, "edge_count": cluster_graph[src][cluster]["weight"]}
        for src in cluster_graph.predecessors(cluster)
    ]
    outbound = [
        {"cluster": dst, "edge_count": cluster_graph[cluster][dst]["weight"]}
        for dst in cluster_graph.successors(cluster)
    ]

    return {
        "cluster": cluster,
        "file_count": len(members),
        "files": [
            {"module": m, "one_liner": _one_liner_for(graph, m, l0_notes)}
            for m in members_by_indegree[:max_files_listed]
        ],
        "external_deps": sorted(external_deps)[:20],
        "inbound_clusters": sorted(inbound, key=lambda x: -x["edge_count"]),
        "outbound_clusters": sorted(outbound, key=lambda x: -x["edge_count"]),
        "valid_neighbor_clusters": {c["cluster"] for c in inbound} | {c["cluster"] for c in outbound},
    }


def build_overview_facts(
    cluster_summaries: dict[str, dict], cluster_graph: nx.DiGraph, instability: dict[str, float]
) -> dict:
    entry_points = [
        c for c in cluster_graph.nodes() if cluster_graph.in_degree(c) == 0 and cluster_graph.out_degree(c) > 0
    ]
    largest = sorted(cluster_summaries.keys(), key=lambda c: instability.get(c, 0), reverse=False)

    return {
        "cluster_count": cluster_graph.number_of_nodes(),
        "entry_point_clusters": entry_points[:10],
        "most_stable_clusters": largest[:10],
        "cluster_roles": {
            name: summary.get("role", "") for name, summary in cluster_summaries.items()
        },
        "valid_cluster_names": set(cluster_summaries.keys()),
    }
