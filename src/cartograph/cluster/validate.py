"""Cluster quality metrics used without ground truth: modularity and stability.

Stability perturbs the edge set and re-clusters, then measures agreement
via the adjusted Rand index. A clustering that collapses under a 5% edge
drop is not a real finding, whatever its modularity says.
"""

from __future__ import annotations

import random
from collections import Counter
from math import comb

import networkx as nx

from cartograph.cluster.hybrid import cluster_graph


def _adjusted_rand_index(labels_a: list[str], labels_b: list[str]) -> float:
    """Minimal ARI implementation — avoids pulling in scikit-learn for one metric."""
    contingency: dict[tuple[str, str], int] = Counter(zip(labels_a, labels_b))
    row_totals: dict[str, int] = Counter(labels_a)
    col_totals: dict[str, int] = Counter(labels_b)
    n = len(labels_a)

    sum_comb_c = sum(comb(count, 2) for count in contingency.values())
    sum_comb_rows = sum(comb(count, 2) for count in row_totals.values())
    sum_comb_cols = sum(comb(count, 2) for count in col_totals.values())
    total_comb = comb(n, 2)

    expected = (sum_comb_rows * sum_comb_cols) / total_comb if total_comb else 0
    max_index = (sum_comb_rows + sum_comb_cols) / 2
    denom = max_index - expected
    if denom == 0:
        return 1.0
    return (sum_comb_c - expected) / denom


def modularity(graph: nx.MultiDiGraph, assignment: dict[str, str]) -> float:
    undirected = nx.Graph(graph)
    communities: dict[str, set[str]] = {}
    for module, cluster in assignment.items():
        communities.setdefault(cluster, set()).add(module)
    return nx.algorithms.community.modularity(undirected, communities.values())


def stability_score(graph: nx.MultiDiGraph, runs: int = 10, drop_fraction: float = 0.05, seed: int = 0) -> float:
    """Mean pairwise ARI across `runs` re-clusterings with 5% of edges dropped."""
    rng = random.Random(seed)
    edges = list(graph.edges())
    if len(edges) < 10:
        return 1.0

    nodes = list(graph.nodes())
    assignments = []
    for _ in range(runs):
        drop_count = int(len(edges) * drop_fraction)
        dropped = set(rng.sample(range(len(edges)), drop_count))
        perturbed = nx.MultiDiGraph()
        perturbed.add_nodes_from(nodes)
        for i, (src, dst) in enumerate(edges):
            if i not in dropped:
                perturbed.add_edge(src, dst)
        assignment = cluster_graph(perturbed)
        assignments.append([assignment[n] for n in nodes])

    scores = []
    for i in range(len(assignments)):
        for j in range(i + 1, len(assignments)):
            scores.append(_adjusted_rand_index(assignments[i], assignments[j]))

    return sum(scores) / len(scores) if scores else 1.0
