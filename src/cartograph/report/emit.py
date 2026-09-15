"""Milestone-1 report: just the graph and the resolution quality metric.

No clustering, no LLM, no risk map yet — those land in later milestones.
This is deliberately the smallest useful JSON output: node/edge counts
and an unresolved-import percentage, which is the milestone-1 acceptance
test (<5% on flask/fastapi).
"""

from __future__ import annotations

import networkx as nx

from cartograph.models import ResolutionResult


def build_report(
    result: ResolutionResult,
    graph: nx.MultiDiGraph,
    clusters: dict[str, str] | None = None,
    risk: dict | None = None,
) -> dict:
    nodes = [
        {
            "module": name,
            "path": data["path"],
            "loc": data["loc"],
            "symbols": data["symbols"],
            "external_deps": data["external_deps"],
            "unresolved": data["unresolved"],
            "cluster": clusters.get(name) if clusters else None,
        }
        for name, data in graph.nodes(data=True)
    ]
    edges = [{"src": src, "dst": dst} for src, dst in graph.edges()]

    report = {
        "summary": {
            "file_count": len(result.files),
            "internal_edge_count": graph.number_of_edges(),
            "unresolved_ratio": round(result.unresolved_ratio, 4),
            "cluster_count": len(set(clusters.values())) if clusters else 0,
        },
        "nodes": nodes,
        "edges": edges,
    }
    if risk is not None:
        report["risk"] = risk
    return report
