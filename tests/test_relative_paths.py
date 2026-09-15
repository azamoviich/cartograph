"""Regression test for a real bug: resolved file paths were absolute,
leaking the ephemeral clone directory (e.g. a local /tmp/cartograph-xxx
path) into every report — including the ones committed for the demo
site. Paths must be repo-relative.
"""

from __future__ import annotations

from pathlib import Path

from cartograph.resolve.javascript import resolve_javascript_repo
from cartograph.resolve.python import resolve_python_repo

PYTHON_FIXTURE = Path(__file__).parent / "fixtures"
JS_FIXTURE = Path(__file__).parent / "fixtures_js"


def test_python_paths_are_repo_relative():
    result = resolve_python_repo(PYTHON_FIXTURE)
    for f in result.files:
        assert not Path(f.path).is_absolute(), f.path
        assert "cartograph-" not in f.path


def test_javascript_paths_are_repo_relative():
    result = resolve_javascript_repo(JS_FIXTURE)
    for f in result.files:
        assert not Path(f.path).is_absolute(), f.path
        assert "cartograph-" not in f.path
