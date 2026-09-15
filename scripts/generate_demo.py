"""Regenerate docs/reports/*.json — the pre-generated reports the demo
site (served via GitHub Pages from docs/) reads so a visitor without an
API key sees instant results.

Run after any resolver/cluster/risk change to keep the demo current:

    uv run python scripts/generate_demo.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cartograph.cluster.hybrid import build_cluster_level_graph, cluster_graph  # noqa: E402
from cartograph.graph.build import build_module_graph  # noqa: E402
from cartograph.ingest.clone import clone_repo  # noqa: E402
from cartograph.report.emit import build_report  # noqa: E402
from cartograph.resolve.javascript import resolve_javascript_repo  # noqa: E402
from cartograph.resolve.python import resolve_python_repo  # noqa: E402
from cartograph.risk.build import build_risk_map  # noqa: E402

# (slug, clone URL, resolver)
DEMO_REPOS = [
    ("pallets-flask", "https://github.com/pallets/flask", resolve_python_repo),
    ("tiangolo-fastapi", "https://github.com/tiangolo/fastapi", resolve_python_repo),
    ("expressjs-express", "https://github.com/expressjs/express", resolve_javascript_repo),
    ("colinhacks-zod", "https://github.com/colinhacks/zod", resolve_javascript_repo),
]

OUTPUT_DIR = REPO_ROOT / "docs" / "reports"


def generate_one(slug: str, url: str, resolver) -> dict:
    with tempfile.TemporaryDirectory(prefix="cartograph-demo-") as tmp:
        repo_root = clone_repo(url, Path(tmp) / slug)
        result = resolver(repo_root)
        graph = build_module_graph(result)
        assignment = cluster_graph(graph)
        cluster_level_graph = build_cluster_level_graph(graph, assignment)
        risk = build_risk_map(graph, cluster_level_graph, repo_root)
        return build_report(result, graph, clusters=assignment, risk=risk)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    index = []

    for slug, url, resolver in DEMO_REPOS:
        print(f"generating {slug} ...", flush=True)
        report = generate_one(slug, url, resolver)
        out_path = OUTPUT_DIR / f"{slug}.json"
        out_path.write_text(json.dumps(report))
        summary = report["summary"]
        print(
            f"  files={summary['file_count']} edges={summary['internal_edge_count']} "
            f"clusters={summary['cluster_count']} unresolved={summary['unresolved_ratio']:.2%}"
        )
        index.append(
            {
                "slug": slug,
                "title": url.replace("https://github.com/", ""),
                "url": url,
                "file_count": summary["file_count"],
                "cluster_count": summary["cluster_count"],
                "unresolved_ratio": summary["unresolved_ratio"],
            }
        )

    (OUTPUT_DIR / "index.json").write_text(json.dumps(index, indent=2))
    print(f"wrote {len(index)} reports + index.json to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
