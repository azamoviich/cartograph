"""Directory-prior + graph-corrector clustering.

Pure Louvain/Leiden on the import graph produces topologically valid but
unnameable clusters. Directories are the prior; the graph only merges
directories that are actually one coupled subsystem (e.g. `utils/` +
`helpers/`) or splits a directory that turns out to hold two unrelated
subsystems.
"""

from __future__ import annotations

from collections import defaultdict

import igraph as ig
import leidenalg
import networkx as nx


def _cluster_sizes(assignment: dict[str, str]) -> dict[str, int]:
    sizes: dict[str, int] = defaultdict(int)
    for cluster in assignment.values():
        sizes[cluster] += 1
    return sizes


def _cross_cluster_edge_counts(
    graph: nx.MultiDiGraph, assignment: dict[str, str]
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for src, dst in graph.edges():
        ca, cb = assignment[src], assignment[dst]
        if ca == cb:
            continue
        key = (ca, cb) if ca < cb else (cb, ca)
        counts[key] += 1
    return counts


def _intra_cluster_edge_counts(graph: nx.MultiDiGraph, assignment: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for src, dst in graph.edges():
        if assignment[src] == assignment[dst]:
            counts[assignment[src]] += 1
    return counts


def _density(edge_count: int, size: int) -> float:
    if size <= 1:
        return 0.0
    possible = size * (size - 1)
    return edge_count / possible


def merge_coupled_clusters(
    graph: nx.MultiDiGraph, assignment: dict[str, str], max_iterations: int | None = None
) -> dict[str, str]:
    """Merge cluster pairs whose mutual coupling exceeds their own intra-cluster density.

    Each iteration merges exactly one pair (the strongest), so the cap
    must scale with the number of clusters — at most (cluster_count - 1)
    merges can ever happen before everything collapses into one cluster.
    """
    assignment = dict(assignment)
    if max_iterations is None:
        max_iterations = len(set(assignment.values()))

    for _ in range(max_iterations):
        sizes = _cluster_sizes(assignment)
        intra_edges = _intra_cluster_edge_counts(graph, assignment)
        cross_edges = _cross_cluster_edge_counts(graph, assignment)

        best_pair = None
        best_margin = 0.0
        for (a, b), count in cross_edges.items():
            coupling = count / (sizes[a] * sizes[b])
            threshold = max(
                _density(intra_edges.get(a, 0), sizes[a]),
                _density(intra_edges.get(b, 0), sizes[b]),
                1e-9,
            )
            margin = coupling - threshold
            if margin > best_margin:
                best_margin = margin
                best_pair = (a, b)

        if best_pair is None:
            break

        a, b = best_pair
        for module, cluster in assignment.items():
            if cluster == b:
                assignment[module] = a

    return assignment


def _induced_undirected_igraph(graph: nx.MultiDiGraph, members: list[str]) -> tuple[ig.Graph, list[str]]:
    index = {m: i for i, m in enumerate(members)}
    weights: dict[tuple[int, int], int] = defaultdict(int)
    for src, dst in graph.subgraph(members).edges():
        i, j = index[src], index[dst]
        key = (i, j) if i < j else (j, i)
        weights[key] += 1

    g = ig.Graph(n=len(members))
    g.add_edges(list(weights.keys()))
    g.es["weight"] = list(weights.values())
    return g, members


def split_incoherent_clusters(
    graph: nx.MultiDiGraph,
    assignment: dict[str, str],
    min_size: int = 6,
    max_cross_fraction: float = 0.1,
) -> dict[str, str]:
    """Split a directory-seeded cluster if Leiden finds near-disconnected subcommunities in it."""
    assignment = dict(assignment)
    sizes = _cluster_sizes(assignment)

    for cluster, size in list(sizes.items()):
        if size < min_size:
            continue
        members = [m for m, c in assignment.items() if c == cluster]
        ig_graph, ordered_members = _induced_undirected_igraph(graph, members)
        if ig_graph.ecount() == 0:
            continue

        partition = leidenalg.find_partition(
            ig_graph, leidenalg.ModularityVertexPartition, weights="weight", seed=42
        )
        if len(partition) < 2:
            continue

        total_edges = ig_graph.ecount()
        cross_edges = sum(1 for e in ig_graph.es if partition.membership[e.source] != partition.membership[e.target])
        if cross_edges / total_edges > max_cross_fraction:
            continue

        for member, part_idx in zip(ordered_members, partition.membership):
            assignment[member] = f"{cluster}#{part_idx}"

    return assignment


def cluster_graph(graph: nx.MultiDiGraph) -> dict[str, str]:
    from cartograph.cluster.directory import seed_by_directory

    assignment = seed_by_directory(graph)
    assignment = merge_coupled_clusters(graph, assignment)
    assignment = split_incoherent_clusters(graph, assignment)
    return assignment


def build_cluster_level_graph(graph: nx.MultiDiGraph, assignment: dict[str, str]) -> nx.DiGraph:
    """Collapse the module graph into a cluster-level DAG-ish graph (may still contain cycles)."""
    cg = nx.DiGraph()
    for cluster in set(assignment.values()):
        cg.add_node(cluster)

    for src, dst in graph.edges():
        ca, cb = assignment[src], assignment[dst]
        if ca == cb:
            continue
        if cg.has_edge(ca, cb):
            cg[ca][cb]["weight"] += 1
        else:
            cg.add_edge(ca, cb, weight=1)

    return cg
