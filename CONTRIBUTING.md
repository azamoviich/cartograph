# Contributing

## Setup

```
git clone https://github.com/azamoviich/cartograph.git
cd cartograph
uv sync
```

## Running tests

```
uv run pytest
```

## Linting

```
uv run ruff check src tests
```

CI runs both on every push and PR (`.github/workflows/ci.yml`), against Python 3.11–3.13.

## Where things live

- `src/cartograph/ingest/` — cloning and file discovery
- `src/cartograph/parse/` — tree-sitter parsing, one module per language
- `src/cartograph/resolve/` — import-string-to-file-edge resolution, one module per language
- `src/cartograph/graph/` — builds the networkx module graph from a `ResolutionResult`
- `src/cartograph/cluster/` — directory-prior + Leiden hybrid clustering
- `src/cartograph/risk/` — god files, cycles, ownership, test proximity, SDP violations
- `src/cartograph/narrate/` — grounded LLM narration (BYO API key)
- `src/cartograph/report/` — JSON + HTML report emission
- `demo/` — the static demo site; `scripts/generate_demo.py` regenerates its committed reports

## Adding a language

A resolver's only contract is: take a repo root, return a `ResolutionResult` (a list of
`ParsedFile` plus a list of `ResolvedEdge`). Everything downstream — graph, clustering, risk,
narration, report — is language-agnostic. Look at `resolve/python.py` (dotted module names) and
`resolve/javascript.py` (path-based module names) as two different conventions for the same
contract before adding a third.

## Test fixtures

`tests/fixtures*/` directories contain deliberately minimal, sometimes deliberately "wrong" code
(unused imports, `TYPE_CHECKING` guards, a real import cycle) used as parser/resolver test input —
they're excluded from lint for that reason. Don't clean them up.

## Philosophy

Every fact in a report should be traceable to either a computed graph/git property or, for
narration, an LLM claim that cites a real neighbor from the facts it was given. If you're adding a
feature that makes something up without grounding it in one of those, it probably needs a citation
mechanism, not just a prompt.
