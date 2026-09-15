"""Regression test for a real bug: directory-seed clustering split module
names on "." only, which is correct for Python's dotted names but wrong
for JS/TS's slash-separated paths — every JS module became its own
singleton seed cluster, silently defeating directory-prior clustering
(seen on express: 87 near-singleton clusters for 141 files, dropping to
68 real ones once "/" was also treated as a separator).
"""

from __future__ import annotations

import networkx as nx

from cartograph.cluster.directory import seed_by_directory


def _js_style_graph() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for name in ["src/lib/a", "src/lib/b", "src/lib/c", "src/routes/x", "src/routes/y"]:
        g.add_node(name, loc=10, symbols=[])
    return g


def test_slash_separated_module_names_group_by_directory():
    graph = _js_style_graph()
    assignment = seed_by_directory(graph, max_group_fraction=0.7)

    # lib/* and routes/* should each land in one seed group, not five
    # singleton groups keyed by their full (unsplit-on-".") path.
    assert assignment["src/lib/a"] == assignment["src/lib/b"] == assignment["src/lib/c"]
    assert assignment["src/routes/x"] == assignment["src/routes/y"]
    assert assignment["src/lib/a"] != assignment["src/routes/x"]


def test_root_index_module_name_does_not_produce_empty_key():
    graph = nx.MultiDiGraph()
    graph.add_node(".", loc=5, symbols=[])
    graph.add_node("src/app", loc=5, symbols=[])

    assignment = seed_by_directory(graph)

    assert assignment["."] != ""
