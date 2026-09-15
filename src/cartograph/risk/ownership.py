"""Ownership concentration ("bus factor"), from git history.

Deliberately not called "bus factor" in the UI-facing summary — that
name overclaims. Squashed merges attribute everything to whoever
clicked merge, bot commits skew authorship, and email aliasing without
.mailmap fragments one person into several. This computes the weaker,
defensible claim: which single author's commits dominate each file's
recent history.

Uses `git log --name-only`, never `git blame` (O(files × history),
destroyed by reformatting) and never `--numstat`: the repo is cloned
with `--filter=blob:none`, so `--numstat` (which needs blob contents to
count changed lines) triggers an on-demand network fetch of every
touched blob — turning a local command into thousands of round trips.
`--name-only` only needs tree diffs, which are already local.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

_BOT_PATTERN = re.compile(r"\bbot\b|\[bot\]|dependabot|renovate", re.IGNORECASE)
_MIN_COMMITS = 5


_GIT_LOG_TIMEOUT_SECONDS = 45
_MAX_COMMITS = 3000  # a high-churn repo (many translated docs, etc.) can otherwise take minutes to parse


def _run_git_log(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "--no-merges",
                "--use-mailmap",
                f"--max-count={_MAX_COMMITS}",
                "--format=COMMIT\t%H\t%aN\t%aE",
                "--name-only",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_LOG_TIMEOUT_SECONDS,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        # Ownership is a nice-to-have risk signal, not load-bearing — degrade
        # to "no data" rather than blocking the whole analysis.
        return ""


def compute_ownership(repo_root: Path) -> dict[str, dict]:
    """Return {relative_file_path: {"top_author": str, "share": float, "commit_count": int}}."""
    output = _run_git_log(repo_root)
    if not output:
        return {}

    file_authors: dict[str, Counter] = defaultdict(Counter)
    current_author: str | None = None

    for line in output.splitlines():
        if line.startswith("COMMIT\t"):
            _, _commit_hash, name, email = line.split("\t", 3)
            current_author = None if _BOT_PATTERN.search(name) or _BOT_PATTERN.search(email) else name
            continue
        if current_author is None or not line.strip():
            continue
        file_authors[line][current_author] += 1

    ownership: dict[str, dict] = {}
    for path, authors in file_authors.items():
        total = sum(authors.values())
        if total < _MIN_COMMITS:
            continue
        top_author, top_count = authors.most_common(1)[0]
        ownership[path] = {
            "top_author": top_author,
            "share": round(top_count / total, 3),
            "commit_count": total,
        }

    return ownership
