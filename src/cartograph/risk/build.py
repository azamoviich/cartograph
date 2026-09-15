"""Aggregate all risk signals into one report section."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from cartograph.risk.cycles import find_cycles
from cartograph.risk.god_files import find_god_files
from cartograph.risk.layering import find_sdp_violations
from cartograph.risk.ownership import compute_ownership
from cartograph.risk.test_proximity import find_untested_hot_paths


def _churn_hotspots(graph: nx.MultiDiGraph, ownership: dict[str, dict], top_fraction: float = 0.1) -> list[dict]:
    """Files with both high commit churn and high LOC — the well-regarded cheap signal."""
    path_to_module = {d["path"]: n for n, d in graph.nodes(data=True)}
    scored = []
    for path, info in ownership.items():
        module = path_to_module.get(path)
        if module is None:
            continue
        loc = graph.nodes[module]["loc"]
        scored.append((module, info["commit_count"], loc))

    if not scored:
        return []

    max_commits = max(s[1] for s in scored) or 1
    max_loc = max(s[2] for s in scored) or 1
    ranked = sorted(scored, key=lambda s: (s[1] / max_commits) * (s[2] / max_loc), reverse=True)
    cutoff = max(1, int(len(ranked) * top_fraction))
    return [{"module": m, "commit_count": c, "loc": loc} for m, c, loc in ranked[:cutoff]]


def build_risk_map(graph: nx.MultiDiGraph, cluster_graph: nx.DiGraph, repo_root: Path) -> dict:
    ownership = compute_ownership(repo_root)

    return {
        "god_files": find_god_files(graph),
        "cycles": find_cycles(graph),
        "ownership_concentration": [
            {"path": path, **info} for path, info in sorted(
                ownership.items(), key=lambda kv: kv[1]["share"], reverse=True
            )[:25]
        ],
        "untested_hot_paths": find_untested_hot_paths(graph),
        "sdp_violations": find_sdp_violations(cluster_graph),
        "churn_hotspots": _churn_hotspots(graph, ownership),
    }
