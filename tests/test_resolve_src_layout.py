"""Regression test for a real bug hit on flask: files outside the detected
src/ layout (example scripts, docs configs) used to be named by bare
filename stem, so two files sharing a name (e.g. two `conftest.py` in
different example apps) collapsed into one graph node.
"""

from __future__ import annotations

from pathlib import Path

from cartograph.resolve.python import resolve_python_repo

FIXTURE_ROOT = Path(__file__).parent / "fixtures_src_layout"


def test_files_outside_src_get_distinct_module_names():
    result = resolve_python_repo(FIXTURE_ROOT)
    modules = {f.module_name for f in result.files}
    assert "scripts.a.conftest" in modules
    assert "scripts.b.conftest" in modules
    assert len(modules) == len(result.files)  # no collisions at all


def test_src_layout_still_used_for_package_files():
    result = resolve_python_repo(FIXTURE_ROOT)
    modules = {f.module_name for f in result.files}
    assert "mypkg" in modules
    assert "mypkg.mod" in modules
