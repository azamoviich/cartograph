"""Milestone-1 report: just the graph and the resolution quality metric.

No clustering, no LLM, no risk map yet — those land in later milestones.
This is deliberately the smallest useful JSON output: node/edge counts
and an unresolved-import percentage, which is the milestone-1 acceptance
test (<5% on flask/fastapi).
"""

from __future__ import annotations

import networkx as nx

from cartograph.models import ResolutionResult


def build_report(result: ResolutionResult, graph: nx.MultiDiGraph) -> dict:
    nodes = [
        {
            "module": name,
            "path": data["path"],
            "loc": data["loc"],
            "symbols": data["symbols"],
            "external_deps": data["external_deps"],
            "unresolved": data["unresolved"],
        }
        for name, data in graph.nodes(data=True)
    ]
    edges = [{"src": src, "dst": dst} for src, dst in graph.edges()]

    return {
        "summary": {
            "file_count": len(result.files),
            "internal_edge_count": graph.number_of_edges(),
            "unresolved_ratio": round(result.unresolved_ratio, 4),
        },
        "nodes": nodes,
        "edges": edges,
    }
