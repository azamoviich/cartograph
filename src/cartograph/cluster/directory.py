"""Directory-prior clustering seed.

Directory structure already encodes most of the human vocabulary for a
codebase's subsystems ("routing", "middleware"). We use dotted module
name prefixes (not raw filesystem paths) as the directory proxy, since
module names are already normalized against src/flat layout by the
resolve stage.
"""

from __future__ import annotations

import re
from collections import defaultdict

import networkx as nx

# Python module names are dotted ("pkg.sub.mod"); JS/TS module names are
# POSIX paths ("src/sub/mod"). Splitting on "." alone silently treats
# every JS module as a single, unsplittable path segment — every module
# becomes its own seed cluster, defeating directory-prior clustering
# entirely. Split on either separator so this works for both languages.
_SEPARATOR = re.compile(r"[./]")


def _split(module_name: str) -> list[str]:
    if module_name in (".", ""):
        return ["<root>"]
    return [p for p in _SEPARATOR.split(module_name) if p]


def _group_by_depth(nodes: list[str], depth: int) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        parts = _split(n)
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
