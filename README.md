# Cartograph

Point it at any repo, get an auto-generated architecture explanation: an interactive dependency
diagram, prose describing each subsystem, and a risk map (god files, circular dependencies,
ownership concentration, layering violations).

Status: early development. Milestone 1 (Python import resolution → dependency graph JSON) in progress.

## Usage

```
uv run cartograph analyze https://github.com/pallets/flask
uv run cartograph analyze /path/to/local/repo -o report.json
```
