"""L0 -> L1 -> L2 bottom-up narration, grounded and cached.

Never ask "what design patterns does this use?" — that's pure invention
bait. Every prompt asks the model to explain facts it was handed, not to
infer facts it wasn't.
"""

from __future__ import annotations

import json

import networkx as nx

from cartograph.narrate.cache import DiskCache
from cartograph.narrate.citations import enforce_cluster_citations, enforce_overview_citations
from cartograph.narrate.client import (
    DEFAULT_L0_MODEL,
    DEFAULT_L1_MODEL,
    DEFAULT_L2_MODEL,
    NarrationClient,
)
from cartograph.narrate.facts import build_cluster_facts, build_overview_facts, select_l0_candidates
from cartograph.narrate.schemas import ClusterSummary, FileNote, RepoOverview
from cartograph.risk.layering import compute_instability

_L0_SYSTEM = (
    "You summarize a single source file in one short sentence based only on its "
    "top-level symbol names. Do not guess behavior beyond what the names imply."
)

_L1_SYSTEM = (
    "You are documenting one subsystem (cluster of files) in a codebase for an "
    "engineer seeing it for the first time. You are given only facts computed from "
    "the import graph and git history — not source code. Every entry in "
    "provides_to/depends_on must name a cluster from the provided neighbor list; "
    "never invent a cluster name. State only what the given facts support."
)

_L2_SYSTEM = (
    "You write a short architecture overview for a repository from per-subsystem "
    "summaries and graph facts. key_subsystems must only name clusters from the "
    "provided list. Do not describe design patterns or behavior you were not told."
)


def _run_l0(
    graph: nx.MultiDiGraph, client: NarrationClient, cache: DiskCache, model: str
) -> dict[str, str]:
    notes: dict[str, str] = {}
    for module in select_l0_candidates(graph):
        symbols = graph.nodes[module].get("symbols") or []
        user = json.dumps({"module": module, "symbols": symbols[:20]})
        cached = cache.get(model, _L0_SYSTEM, user)
        if cached is not None:
            notes[module] = cached["one_liner"]
            continue
        note = client.structured(_L0_SYSTEM, user, FileNote, model)
        cache.set(model, _L0_SYSTEM, user, note.model_dump())
        notes[module] = note.one_liner
    return notes


def _run_l1(
    graph: nx.MultiDiGraph,
    assignment: dict[str, str],
    cluster_graph: nx.DiGraph,
    l0_notes: dict[str, str],
    client: NarrationClient,
    cache: DiskCache,
    model: str,
) -> dict[str, ClusterSummary]:
    summaries: dict[str, ClusterSummary] = {}
    for cluster in cluster_graph.nodes():
        facts = build_cluster_facts(cluster, graph, assignment, cluster_graph, l0_notes)
        valid_neighbors = facts.pop("valid_neighbor_clusters")
        user = json.dumps(facts, sort_keys=True)

        cached = cache.get(model, _L1_SYSTEM, user)
        if cached is not None:
            summary = ClusterSummary.model_validate(cached)
        else:
            summary = client.structured(_L1_SYSTEM, user, ClusterSummary, model)
            cache.set(model, _L1_SYSTEM, user, summary.model_dump())

        summaries[cluster] = enforce_cluster_citations(summary, valid_neighbors)
    return summaries


def _run_l2(
    cluster_summaries: dict[str, ClusterSummary],
    cluster_graph: nx.DiGraph,
    client: NarrationClient,
    cache: DiskCache,
    model: str,
) -> RepoOverview:
    instability = compute_instability(cluster_graph)
    summaries_as_dicts = {name: s.model_dump() for name, s in cluster_summaries.items()}
    facts = build_overview_facts(summaries_as_dicts, cluster_graph, instability)
    valid_clusters = facts.pop("valid_cluster_names")
    user = json.dumps(facts, sort_keys=True)

    cached = cache.get(model, _L2_SYSTEM, user)
    if cached is not None:
        overview = RepoOverview.model_validate(cached)
    else:
        overview = client.structured(_L2_SYSTEM, user, RepoOverview, model)
        cache.set(model, _L2_SYSTEM, user, overview.model_dump())

    return enforce_overview_citations(overview, valid_clusters)


def narrate_repo(
    graph: nx.MultiDiGraph,
    assignment: dict[str, str],
    cluster_graph: nx.DiGraph,
    client: NarrationClient,
    cache: DiskCache,
    l0_model: str = DEFAULT_L0_MODEL,
    l1_model: str = DEFAULT_L1_MODEL,
    l2_model: str = DEFAULT_L2_MODEL,
) -> dict:
    l0_notes = _run_l0(graph, client, cache, l0_model)
    cluster_summaries = _run_l1(graph, assignment, cluster_graph, l0_notes, client, cache, l1_model)
    overview = _run_l2(cluster_summaries, cluster_graph, client, cache, l2_model)

    return {
        "overview": overview.model_dump(),
        "clusters": {name: s.model_dump() for name, s in cluster_summaries.items()},
    }
