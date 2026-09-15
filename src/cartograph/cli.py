from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import click

from cartograph.graph.build import build_module_graph
from cartograph.ingest.clone import clone_repo, repo_slug
from cartograph.report.emit import build_report
from cartograph.resolve.python import resolve_python_repo


@click.group()
def main() -> None:
    """Cartograph: auto-generated architecture docs for any repo."""


@main.command()
@click.argument("source")
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None)
def analyze(source: str, output: Path | None) -> None:
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
        report = build_report(result, graph)

        text = json.dumps(report, indent=2)
        if output:
            output.write_text(text)
            click.echo(f"Wrote report to {output}")
        else:
            click.echo(text)

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
