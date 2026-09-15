"""Directory-prior clustering seed.

Directory structure already encodes most of the human vocabulary for a
codebase's subsystems ("routing", "middleware"). We use dotted module
name prefixes (not raw filesystem paths) as the directory proxy, since
module names are already normalized against src/flat layout by the
resolve stage.
"""

from __future__ import annotations

from collections import defaultdict

import networkx as nx


def _group_by_depth(nodes: list[str], depth: int) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        parts = n.split(".")
        key = ".".join(parts[:depth]) if len(parts) > depth else n
        groups[key].append(n)
    return groups


def seed_by_directory(
    graph: nx.MultiDiGraph, max_group_fraction: float = 0.25, max_depth: int = 6
) -> dict[str, str]:
    """Assign each module to a seed cluster keyed by its dotted-prefix directory.

    Descends to a deeper prefix only while the largest group still
    dominates the repo, so flat-layout repos (few top-level packages)
    still end up with multiple groups instead of one giant one.
    """
    nodes = list(graph.nodes())
    if not nodes:
        return {}

    depth = 1
    groups = _group_by_depth(nodes, depth)
    while depth < max_depth:
        largest = max(len(members) for members in groups.values())
        if largest / len(nodes) <= max_group_fraction:
            break
        depth += 1
        groups = _group_by_depth(nodes, depth)

    return {member: key for key, members in groups.items() for member in members}
