"""Disk cache for narration calls, keyed by a hash of the exact prompt inputs.

Keeps re-running `analyze --narrate` on an unchanged repo free, and lets
the milestone-6 pre-generated demo reports be regenerated deterministically
without re-spending API budget unless the underlying facts actually changed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class DiskCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(model: str, system: str, user: str) -> str:
        payload = json.dumps({"model": model, "system": system, "user": user}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, model: str, system: str, user: str) -> dict | None:
        path = self.cache_dir / f"{self._key(model, system, user)}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def set(self, model: str, system: str, user: str, value: dict) -> None:
        path = self.cache_dir / f"{self._key(model, system, user)}.json"
        path.write_text(json.dumps(value, indent=2))
