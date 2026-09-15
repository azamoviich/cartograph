"""Regression test for a real bug: the merge loop capped at a fixed low
iteration count regardless of graph size, so a repo needing many merges
(flask needed ~20+) got stuck far short of convergence.
"""

from __future__ import annotations

import networkx as nx

from cartograph.cluster.hybrid import merge_coupled_clusters


def _disjoint_pairs_graph(pair_count: int) -> nx.MultiDiGraph:
    """`pair_count` independent, internally-coupled pairs — each pair should merge
    into one cluster, but the loop only merges one pair per iteration (the
    single strongest candidate), so this needs `pair_count` iterations total.
    """
    g = nx.MultiDiGraph()
    for i in range(pair_count):
        a, b = f"a{i}", f"b{i}"
        g.add_node(a, loc=10, symbols=[])
        g.add_node(b, loc=10, symbols=[])
        g.add_edge(a, b)
        g.add_edge(b, a)
    return g


def test_fixed_low_cap_stops_short_of_convergence():
    pair_count = 30
    graph = _disjoint_pairs_graph(pair_count)
    assignment = {n: n for n in graph.nodes()}  # every node its own seed cluster

    merged = merge_coupled_clusters(graph, assignment, max_iterations=10)

    # Only 10 of the 30 independent pairs can merge in 10 iterations —
    # this is the exact shape of the bug seen on flask (a fixed cap of 20
    # stopped short of merging every pair the algorithm judged coupled).
    assert len(set(merged.values())) == pair_count * 2 - 10


def test_default_iteration_cap_scales_with_cluster_count():
    pair_count = 30
    graph = _disjoint_pairs_graph(pair_count)
    assignment = {n: n for n in graph.nodes()}

    merged = merge_coupled_clusters(graph, assignment, max_iterations=None)

    assert len(set(merged.values())) == pair_count
