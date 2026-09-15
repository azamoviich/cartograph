"""Edge-by-edge resolution test against a hand-written fixture repo.

Covers: relative imports, __init__.py re-export forwarding, a
subpackage, an external dependency, and a TYPE_CHECKING-guarded cycle —
the cases called out as highest-risk in the design review.
"""

from __future__ import annotations

from pathlib import Path

from cartograph.models import EdgeKind
from cartograph.resolve.python import resolve_python_repo

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _edge_set(result, kind: EdgeKind | None = None) -> set[tuple[str, str]]:
    return {
        (e.src, e.dst)
        for e in result.edges
        if kind is None or e.kind is kind
    }


def test_module_names_assigned_correctly():
    result = resolve_python_repo(FIXTURE_ROOT)
    modules = {f.module_name for f in result.files}
    assert modules == {
        "sample_pkg",
        "sample_pkg.app",
        "sample_pkg.helpers",
        "sample_pkg.ctx",
        "sample_pkg.sub",
        "sample_pkg.sub.deep",
    }


def test_init_reexports_resolve_to_defining_module():
    result = resolve_python_repo(FIXTURE_ROOT)
    internal = _edge_set(result, EdgeKind.INTERNAL)
    # `from .app import App` / `from .helpers import helper_fn` / `from . import ctx`
    assert ("sample_pkg", "sample_pkg.app") in internal
    assert ("sample_pkg", "sample_pkg.helpers") in internal
    assert ("sample_pkg", "sample_pkg.ctx") in internal


def test_relative_imports_resolve_across_subpackage():
    result = resolve_python_repo(FIXTURE_ROOT)
    internal = _edge_set(result, EdgeKind.INTERNAL)
    assert ("sample_pkg.app", "sample_pkg.helpers") in internal
    assert ("sample_pkg.app", "sample_pkg.sub.deep") in internal
    assert ("sample_pkg.helpers", "sample_pkg.ctx") in internal


def test_type_checking_guarded_cycle_still_resolves():
    # The import is still real and should still be an edge — filtering
    # TYPE_CHECKING imports out of *cycle reporting* is the risk stage's
    # job (milestone 3), not resolution's.
    result = resolve_python_repo(FIXTURE_ROOT)
    internal = _edge_set(result, EdgeKind.INTERNAL)
    assert ("sample_pkg.ctx", "sample_pkg.app") in internal


def test_external_dependency_classified_not_unresolved():
    result = resolve_python_repo(FIXTURE_ROOT)
    external = _edge_set(result, EdgeKind.EXTERNAL)
    assert any(dst.startswith("numpy") for _, dst in external)


def test_no_unresolved_imports_in_fixture():
    result = resolve_python_repo(FIXTURE_ROOT)
    assert result.unresolved_ratio == 0.0
