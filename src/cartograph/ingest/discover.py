"""Enumerate source files, skipping vendored/generated code.

The ignore list is intentionally visible and editable here rather than
buried — vendored code otherwise wrecks every downstream metric (god
files, ownership, cycles all get skewed by generated code that nobody
"wrote").
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

DEFAULT_IGNORE_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    "third_party",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    "migrations",
    "__generated__",
    ".mypy_cache",
    ".pytest_cache",
    "egg-info",
}

DEFAULT_IGNORE_GLOBS = {
    "*.min.js",
    "*_pb2.py",
    "*.generated.py",
}


def _is_ignored(path: Path, root: Path, ignore_dirs: set[str], ignore_globs: set[str]) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(part in ignore_dirs for part in rel_parts):
        return True
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in ignore_globs)


def discover_python_files(
    root: Path,
    ignore_dirs: set[str] | None = None,
    ignore_globs: set[str] | None = None,
) -> list[Path]:
    ignore_dirs = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
    ignore_globs = ignore_globs if ignore_globs is not None else DEFAULT_IGNORE_GLOBS

    return sorted(
        p
        for p in root.rglob("*.py")
        if not _is_ignored(p, root, ignore_dirs, ignore_globs)
    )


JS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")


def discover_js_files(
    root: Path,
    ignore_dirs: set[str] | None = None,
    ignore_globs: set[str] | None = None,
) -> list[Path]:
    ignore_dirs = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
    ignore_globs = ignore_globs if ignore_globs is not None else DEFAULT_IGNORE_GLOBS

    return sorted(
        p
        for p in root.rglob("*")
        if p.suffix in JS_EXTENSIONS
        and not p.name.endswith(".d.ts")
        and not _is_ignored(p, root, ignore_dirs, ignore_globs)
    )
