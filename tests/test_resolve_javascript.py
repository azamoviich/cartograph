"""Edge-by-edge resolution test for the JS/TS resolver fixture.

Covers: relative import to a barrel (index.ts), named export forwarding
through that barrel (`export { helper } from './helper'`), a star
re-export (`export * from './extra'`), a tsconfig `paths` alias
(`@lib/*` -> `src/lib/*`), and an external npm package.
"""

from __future__ import annotations

from pathlib import Path

from cartograph.models import EdgeKind
from cartograph.resolve.javascript import resolve_javascript_repo

FIXTURE_ROOT = Path(__file__).parent / "fixtures_js"


def _edges_of_kind(result, kind: EdgeKind) -> set[tuple[str, str]]:
    return {(e.src, e.dst) for e in result.edges if e.kind is kind}


def test_module_names_use_index_folding():
    result = resolve_javascript_repo(FIXTURE_ROOT)
    modules = {f.module_name for f in result.files}
    assert "src/app" in modules
    assert "src/utils" in modules  # index.ts folds to the directory name
    assert "src/utils/helper" in modules
    assert "src/utils/extra" in modules
    assert "src/lib/widget" in modules


def test_named_export_forwards_through_barrel():
    result = resolve_javascript_repo(FIXTURE_ROOT)
    internal = _edges_of_kind(result, EdgeKind.INTERNAL)
    # `import { helper } from "./utils"` should land on src/utils/helper,
    # not stop at the barrel itself.
    assert ("src/app", "src/utils/helper") in internal


def test_tsconfig_path_alias_resolves():
    result = resolve_javascript_repo(FIXTURE_ROOT)
    internal = _edges_of_kind(result, EdgeKind.INTERNAL)
    assert ("src/app", "src/lib/widget") in internal


def test_external_npm_package_classified_not_unresolved():
    result = resolve_javascript_repo(FIXTURE_ROOT)
    external = _edges_of_kind(result, EdgeKind.EXTERNAL)
    assert ("src/app", "express") in external


def test_ts_extension_rewrite_convention_resolves():
    # `import ... from "./utils/helper.js"` where the real file is
    # helper.ts — the standard TS NodeNext/ESM convention where source
    # imports name the *compiled* .js extension. Without handling this,
    # a large fraction of imports in any modern ESM-target TS repo
    # (zod, most ESM packages) resolve to nothing.
    result = resolve_javascript_repo(FIXTURE_ROOT)
    internal = _edges_of_kind(result, EdgeKind.INTERNAL)
    assert ("src/consumer", "src/utils/helper") in internal


def test_no_unresolved_imports_in_fixture():
    result = resolve_javascript_repo(FIXTURE_ROOT)
    assert result.unresolved_ratio == 0.0
