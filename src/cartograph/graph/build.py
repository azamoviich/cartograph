"""Build the networkx module dependency graph from resolved edges."""

from __future__ import annotations

import networkx as nx

from cartograph.models import EdgeKind, ResolutionResult


def build_module_graph(result: ResolutionResult) -> nx.MultiDiGraph:
    """Internal-only graph: nodes are this repo's modules, edges are resolved imports.

    External and unresolved edges are attached as node attributes rather
    than graph edges, since their "destination" isn't a node we control.
    """
    g = nx.MultiDiGraph()

    for f in result.files:
        g.add_node(f.module_name, path=f.path, loc=f.loc, symbols=list(f.symbols))

    for f in result.files:
        g.nodes[f.module_name].setdefault("external_deps", set())
        g.nodes[f.module_name].setdefault("unresolved", [])

    for edge in result.edges:
        if edge.kind is EdgeKind.INTERNAL:
            if edge.src in g and edge.dst in g:
                g.add_edge(edge.src, edge.dst, raw=edge.raw)
        elif edge.kind is EdgeKind.EXTERNAL:
            if edge.src in g:
                g.nodes[edge.src]["external_deps"].add(edge.dst.split(".")[0])
        else:  # UNRESOLVED
            if edge.src in g:
                g.nodes[edge.src]["unresolved"].append(edge.raw)

    for _, data in g.nodes(data=True):
        data["external_deps"] = sorted(data["external_deps"])

    return g
