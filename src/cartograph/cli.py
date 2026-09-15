from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import click

from cartograph.cluster.hybrid import build_cluster_level_graph, cluster_graph
from cartograph.graph.build import build_module_graph
from cartograph.ingest.clone import clone_repo, repo_slug
from cartograph.narrate.cache import DiskCache
from cartograph.report.emit import build_report
from cartograph.report.html import build_html_report
from cartograph.resolve.python import resolve_python_repo
from cartograph.risk.build import build_risk_map


@click.group()
def main() -> None:
    """Cartograph: auto-generated architecture docs for any repo."""


@main.command()
@click.argument("source")
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None)
@click.option("--html", "html_output", type=click.Path(path_type=Path), default=None,
              help="Also write a self-contained interactive HTML diagram.")
@click.option("--narrate", is_flag=True, default=False,
              help="Add LLM-written subsystem prose. Requires ANTHROPIC_API_KEY (BYO key).")
@click.option("--api-key", default=None, help="Anthropic API key, overrides ANTHROPIC_API_KEY.")
@click.option("--narrate-cache", type=click.Path(path_type=Path), default=Path(".cartograph_cache"),
              help="Directory for cached narration calls (avoids re-spending on unchanged facts).")
def analyze(
    source: str,
    output: Path | None,
    html_output: Path | None,
    narrate: bool,
    api_key: str | None,
    narrate_cache: Path,
) -> None:
    """Analyze a GitHub URL or local path and emit a JSON report."""
    tmp_dir = None
    try:
        if source.startswith(("http://", "https://", "git@")):
            tmp_dir = Path(tempfile.mkdtemp(prefix="cartograph-"))
            repo_root = clone_repo(source, tmp_dir / repo_slug(source))
        else:
            repo_root = Path(source).resolve()

        result = resolve_python_repo(repo_root)
        graph = build_module_graph(result)
        assignment = cluster_graph(graph)
        cluster_level_graph = build_cluster_level_graph(graph, assignment)
        risk = build_risk_map(graph, cluster_level_graph, repo_root)
        report = build_report(result, graph, clusters=assignment, risk=risk)

        if narrate:
            from cartograph.narrate.client import AnthropicNarrationClient
            from cartograph.narrate.pipeline import narrate_repo

            client = AnthropicNarrationClient(api_key=api_key)
            cache = DiskCache(narrate_cache)
            report["narration"] = narrate_repo(graph, assignment, cluster_level_graph, client, cache)

        text = json.dumps(report, indent=2)
        if output:
            output.write_text(text)
            click.echo(f"Wrote report to {output}")
        else:
            click.echo(text)

        if html_output:
            html_output.write_text(build_html_report(report, title=repo_slug(source)))
            click.echo(f"Wrote HTML diagram to {html_output}")

        click.echo(
            f"files={report['summary']['file_count']} "
            f"edges={report['summary']['internal_edge_count']} "
            f"unresolved={report['summary']['unresolved_ratio']:.2%}",
            err=True,
        )
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
