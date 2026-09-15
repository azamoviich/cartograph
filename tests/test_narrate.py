"""Narration tests use a fake client — no network access, no API key.

The parts worth testing are the parts that don't depend on model
quality: that a hallucinated cluster name actually gets stripped, and
that the disk cache actually avoids a second "API" call.
"""

from __future__ import annotations

import networkx as nx

from cartograph.narrate.cache import DiskCache
from cartograph.narrate.citations import enforce_cluster_citations, enforce_overview_citations
from cartograph.narrate.pipeline import narrate_repo
from cartograph.narrate.schemas import ClusterSummary, DependencyClaim, FileNote, RepoOverview


def test_cluster_citation_enforcement_drops_invented_cluster():
    summary = ClusterSummary(
        cluster="a",
        role="does things",
        depends_on=[
            DependencyClaim(target_cluster="b", reason="real neighbor"),
            DependencyClaim(target_cluster="totally_invented", reason="model made this up"),
        ],
    )
    cleaned = enforce_cluster_citations(summary, valid_neighbors={"b"})
    assert [c.target_cluster for c in cleaned.depends_on] == ["b"]


def test_overview_citation_enforcement_drops_invented_cluster():
    overview = RepoOverview(summary="x", key_subsystems=["real", "invented"])
    cleaned = enforce_overview_citations(overview, valid_clusters={"real"})
    assert cleaned.key_subsystems == ["real"]


class _FakeClient:
    """Returns one hallucinated neighbor per cluster call, tracks call count."""

    def __init__(self):
        self.calls = 0

    def structured(self, system, user, schema, model):
        self.calls += 1
        if schema is FileNote:
            return FileNote(module="whatever", one_liner="does a thing")
        if schema is ClusterSummary:
            return ClusterSummary(
                cluster="unused",
                role="handles requests",
                depends_on=[DependencyClaim(target_cluster="nonexistent_cluster", reason="invented")],
            )
        if schema is RepoOverview:
            return RepoOverview(summary="a small repo", key_subsystems=["nonexistent_cluster"])
        raise AssertionError(f"unexpected schema {schema}")


def _two_cluster_graph():
    g = nx.MultiDiGraph()
    g.add_node("pkg.a", loc=10, symbols=["Foo"], docstring=None, external_deps=[], unresolved=[])
    g.add_node("pkg.b", loc=10, symbols=["Bar"], docstring="does bar things", external_deps=[], unresolved=[])
    g.add_edge("pkg.a", "pkg.b")
    assignment = {"pkg.a": "a", "pkg.b": "b"}
    cluster_graph = nx.DiGraph()
    cluster_graph.add_node("a")
    cluster_graph.add_node("b")
    cluster_graph.add_edge("a", "b", weight=1)
    return g, assignment, cluster_graph


def test_narrate_repo_strips_hallucinated_dependencies(tmp_path):
    graph, assignment, cluster_graph = _two_cluster_graph()
    client = _FakeClient()
    cache = DiskCache(tmp_path / "cache")

    result = narrate_repo(graph, assignment, cluster_graph, client, cache)

    for cluster_summary in result["clusters"].values():
        assert cluster_summary["depends_on"] == []  # the invented neighbor was dropped
    assert result["overview"]["key_subsystems"] == []  # invented cluster dropped from overview too


def test_narrate_repo_uses_cache_on_second_run(tmp_path):
    graph, assignment, cluster_graph = _two_cluster_graph()
    client = _FakeClient()
    cache = DiskCache(tmp_path / "cache")

    narrate_repo(graph, assignment, cluster_graph, client, cache)
    first_call_count = client.calls

    narrate_repo(graph, assignment, cluster_graph, client, cache)

    assert client.calls == first_call_count  # second run served entirely from cache
