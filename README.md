<p align="center">
  <img src="docs/assets/logo.jpg" alt="Cartograph logo" width="160">
</p>

# Cartograph

[![CI](https://github.com/azamoviich/cartograph/actions/workflows/ci.yml/badge.svg)](https://github.com/azamoviich/cartograph/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

**Point it at any GitHub repo. Get back an interactive dependency diagram, subsystem
clustering, and a risk map — in under a minute, with no setup.**

Every developer has opened an unfamiliar codebase and had no idea where to start. Cartograph
statically analyzes the real import graph — no execution, no LLM guessing at architecture it
wasn't shown — and turns it into something you can actually explore.

**[Live demo — flask, fastapi, express, zod pre-generated, click and explore →](https://azamoviich.github.io/cartograph/)**

## What it actually does

```
clone --filter=blob:none  →  tree-sitter parse  →  resolve imports to real files
      →  cluster into subsystems  →  compute risk signals  →  (optional) LLM narration
      →  interactive HTML report
```

- **Import resolution** (Python + TypeScript/JavaScript) — relative imports, `__init__.py` /
  barrel-file re-export forwarding, `tsconfig.json` path aliases, src-layout detection. Verified
  at **0–0.7% unresolved** across flask, fastapi, express, and zod.
- **Clustering** — directory structure as the prior, Leiden community detection as the
  corrector: merges genuinely coupled directories (`utils/` + `helpers/`), splits directories
  that turn out to hold two unrelated subsystems.
- **Risk map** — god files (rank-relative, not an absolute LOC threshold), circular
  dependencies (SCC-capped so it can't hang on a hairball, `TYPE_CHECKING`-guarded imports
  excluded), ownership concentration from git history, import-based test-proximity, and
  Stable-Dependencies-Principle violations — purely graph-derived, no domain knowledge needed.
- **Narration** *(opt-in, BYO `ANTHROPIC_API_KEY`)* — an LLM writes subsystem prose, but every
  dependency claim it makes is a structured `{target_cluster, reason}` pair checked against the
  real graph after the call; anything naming a cluster that isn't an actual neighbor is
  mechanically dropped. Entry points are a computed graph fact, never an LLM guess.

## Quickstart

```bash
git clone https://github.com/azamoviich/cartograph.git
cd cartograph
uv sync

uv run cartograph analyze https://github.com/pallets/flask --html out.html
open out.html
```

Add `--narrate` (with `ANTHROPIC_API_KEY` set) for LLM-written subsystem summaries. Add
`--lang python|javascript` to override language auto-detection.

## Verified results

| Repo | Files | Internal edges | Clusters | Unresolved imports |
|---|---|---|---|---|
| [pallets/flask](https://github.com/pallets/flask) | 83 | 299 | 43 | 0.00% |
| [tiangolo/fastapi](https://github.com/tiangolo/fastapi) | 1,138 | 1,674 | 810 | 0.00% |
| [expressjs/express](https://github.com/expressjs/express) | 141 | 159 | 68 | 0.74% |
| [colinhacks/zod](https://github.com/colinhacks/zod) | 518 | 730 | 290 | 0.21% |

Remaining unresolved imports in every case are genuine dynamic `require()`/`import()` calls with
a computed (non-literal) specifier — correctly flagged rather than guessed. Run
`uv run python scripts/generate_demo.py` to regenerate these after a resolver change.

## Design notes

A few decisions worth knowing about if you're reading the code:

- **No backend for the demo.** Reports are pre-generated and committed as JSON; the demo site is
  a static viewer that fetches them by query param. A public "paste any repo URL, we clone it"
  endpoint is a free DoS vector — deliberately avoided.
- **Rank-relative, not absolute, thresholds.** "God file" and similar labels are always computed
  relative to the repo being analyzed, so they mean the same thing on a 80-file repo and a
  1,100-file one.
- **`git log --name-only`, never `--numstat`, against a blob-filtered clone.** `--numstat` needs
  blob contents, which triggers a network fetch per touched file against a `--filter=blob:none`
  clone — an 11-second computation silently became 15+ minutes before this was caught.
- **Two resolvers, one contract.** Python (dotted module names) and JS/TS (path-based module
  names) are completely different resolution strategies behind the same `ResolutionResult`
  shape — see [CONTRIBUTING.md](CONTRIBUTING.md) before adding a third language.

## Status

All 7 planned milestones are complete:

- [x] Python import resolution → dependency graph JSON
- [x] Interactive HTML diagram (D3, force-directed, click-to-inspect)
- [x] Clustering + risk map
- [x] Grounded LLM narration (opt-in)
- [x] TypeScript/JavaScript support
- [x] Static web demo (no backend)
- [x] Repo presentation

Known scope boundaries (documented in code, not silently swallowed): no `pyproject.toml`
package-dir remapping, no `package.json` `exports`-map resolution, file-level rather than
symbol-level granularity, single-language analysis per repo (no merged polyglot graph).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
