"""Fetch a repo locally without pulling full history."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_GITHUB_URL_RE = re.compile(r"github\.com[:/]([^/]+)/([^/.]+)")


def clone_repo(source: str, dest: Path, shallow_since: str = "1.year") -> Path:
    """Clone `source` (a GitHub URL or a local path) into `dest`.

    Uses a blob-filtered, time-shallow clone for remote URLs so a large repo
    (e.g. react at ~500MB full history) stays cheap. Local paths are used
    as-is (read-only; never mutated).
    """
    dest.mkdir(parents=True, exist_ok=True)

    if Path(source).exists():
        return Path(source).resolve()

    subprocess.run(
        [
            "git",
            "clone",
            "--filter=blob:none",
            f"--shallow-since={shallow_since}",
            "--single-branch",
            source,
            str(dest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return dest


def repo_slug(source: str) -> str:
    """Derive a filesystem-safe name from a GitHub URL, e.g. 'pallets/flask'."""
    match = _GITHUB_URL_RE.search(source)
    if match:
        return f"{match.group(1)}__{match.group(2)}"
    return Path(source).stem
