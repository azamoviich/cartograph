"""Resolve JS/TS import specifiers into real file edges.

No PyPI package does faithful Node/TypeScript module resolution (the
design review's suggested `oxc-resolver` doesn't actually exist on
PyPI), so this hand-rolls the high-value subset: relative imports with
extension/index inference, `tsconfig.json` `baseUrl`/`paths` for bare
specifiers, and barrel-file (`export ... from`) forwarding — the JS
analogue of Python's `__init__.py` re-export problem. Full Node
resolution semantics (package.json `exports` maps, conditional exports,
symlinked workspaces) are out of scope for MVP, the same kind of
documented limitation as Python's package-dir remapping.
"""

from __future__ import annotations

from pathlib import Path

import json5

from cartograph.ingest.discover import discover_js_files
from cartograph.models import EdgeKind, ResolutionResult, ResolvedEdge
from cartograph.parse.javascript import parse_javascript_file

_EXTENSION_ORDER = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_MAX_STAR_HOPS = 1


def _module_name_for(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    posix = rel.as_posix()
    if rel.name == "index":
        parent = rel.parent.as_posix()
        return parent if parent != "." else "."
    return posix


def _find_tsconfigs(root: Path) -> dict[Path, dict]:
    """Parse every tsconfig.json, resolving one level of `extends`."""
    configs: dict[Path, dict] = {}
    for path in root.rglob("tsconfig*.json"):
        if "node_modules" in path.parts:
            continue
        try:
            raw = json5.loads(path.read_text())
        except ValueError:
            continue
        options = dict(raw.get("compilerOptions", {}))

        extends = raw.get("extends")
        if isinstance(extends, str) and extends.startswith("."):
            base_path = (path.parent / extends).resolve()
            if not base_path.suffix:
                base_path = base_path.with_suffix(".json")
            if base_path.exists():
                try:
                    base_raw = json5.loads(base_path.read_text())
                    base_options = base_raw.get("compilerOptions", {})
                    options = {**base_options, **options}
                except ValueError:
                    pass

        configs[path.parent] = options
    return configs


def _tsconfig_for(file_path: Path, tsconfigs: dict[Path, dict], root: Path) -> dict | None:
    current = file_path.parent
    while True:
        if current in tsconfigs:
            return tsconfigs[current]
        if current == root or current == current.parent:
            return None
        current = current.parent


_REWRITABLE_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs")


def _try_resolve_on_disk(candidate: Path) -> Path | None:
    if candidate.is_file():
        return candidate

    # TS's NodeNext/ESM convention: source imports use the *compiled*
    # extension ("./foo.js") even though the source file is "./foo.ts" —
    # the extension gets rewritten at build time. Without this, every
    # such import in a modern TS repo (zod, and most ESM-target
    # packages) resolves to nothing.
    if candidate.suffix in _REWRITABLE_EXTENSIONS:
        stripped = candidate.with_suffix("")
        for ext in _EXTENSION_ORDER:
            p = stripped.with_name(stripped.name + ext)
            if p.is_file():
                return p

    for ext in _EXTENSION_ORDER:
        p = candidate.with_name(candidate.name + ext)
        if p.is_file():
            return p
    for ext in _EXTENSION_ORDER:
        p = candidate / f"index{ext}"
        if p.is_file():
            return p
    return None


def _resolve_relative(specifier: str, importer_path: Path) -> Path | None:
    candidate = (importer_path.parent / specifier).resolve()
    return _try_resolve_on_disk(candidate)


def _resolve_via_tsconfig(
    specifier: str, config: dict, config_dir: Path
) -> Path | None:
    base_url = config.get("baseUrl")
    paths = config.get("paths") or {}

    for pattern, targets in paths.items():
        prefix = pattern.replace("*", "")
        if pattern.endswith("*") and specifier.startswith(prefix):
            suffix = specifier[len(prefix) :]
            for target in targets:
                target_path = (config_dir / (base_url or ".") / target.replace("*", suffix)).resolve()
                resolved = _try_resolve_on_disk(target_path)
                if resolved:
                    return resolved
        elif pattern == specifier:
            for target in targets:
                target_path = (config_dir / (base_url or ".") / target).resolve()
                resolved = _try_resolve_on_disk(target_path)
                if resolved:
                    return resolved

    if base_url:
        candidate = (config_dir / base_url / specifier).resolve()
        resolved = _try_resolve_on_disk(candidate)
        if resolved:
            return resolved

    return None


def _external_package_name(specifier: str) -> str:
    if specifier.startswith("@"):
        parts = specifier.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else specifier
    return specifier.split("/")[0]


class _BarrelIndex:
    """Per-module named-export aliases and one-hop star-forwarding targets."""

    def __init__(self):
        self.named_aliases: dict[str, dict[str, str]] = {}  # module -> {exported_name: target_module}
        self.star_targets: dict[str, list[str]] = {}  # module -> [target_module, ...]

    def add(self, module: str, exported_name: str, target_module: str) -> None:
        self.named_aliases.setdefault(module, {})[exported_name] = target_module

    def add_star(self, module: str, target_module: str) -> None:
        self.star_targets.setdefault(module, []).append(target_module)


def resolve_javascript_repo(root: Path) -> ResolutionResult:
    # Candidate paths from filesystem resolution (Path.resolve()) must be
    # compared against a root in the same normalized form, or
    # Path.relative_to raises on symlinked temp dirs (e.g. macOS /tmp).
    root = root.resolve()
    paths = discover_js_files(root)
    parsed = [parse_javascript_file(p) for p in paths]

    for f in parsed:
        f.module_name = _module_name_for(Path(f.path), root)

    module_to_path = {f.module_name: Path(f.path) for f in parsed}
    file_by_module = {f.module_name: f for f in parsed}
    tsconfigs = _find_tsconfigs(root)

    barrels = _BarrelIndex()
    for f in parsed:
        module = f.module_name
        importer_path = Path(f.path)
        for imp in f.imports:
            if not imp.is_export_forward:
                continue
            resolved = _resolve_relative(imp.module, importer_path)
            if resolved is None:
                continue
            target_module = _module_name_for(resolved, root)
            if target_module not in module_to_path:
                continue
            if imp.is_star:
                barrels.add_star(module, target_module)
            for name in imp.names:
                barrels.add(module, name, target_module)

    def _defines_symbol(module: str, name: str) -> bool:
        f = file_by_module.get(module)
        return f is not None and name in f.symbols

    def _resolve_named(module: str, name: str, hops_left: int) -> str | None:
        if _defines_symbol(module, name):
            return module
        alias = barrels.named_aliases.get(module, {}).get(name)
        if alias:
            return alias
        if hops_left > 0:
            for target in barrels.star_targets.get(module, []):
                found = _resolve_named(target, name, hops_left - 1)
                if found:
                    return found
        return None

    edges: list[ResolvedEdge] = []
    for f in parsed:
        module = f.module_name
        importer_path = Path(f.path)
        config = _tsconfig_for(importer_path, tsconfigs, root)
        config_dir = importer_path.parent
        if config is not None:
            for cfg_dir in tsconfigs:
                if config is tsconfigs[cfg_dir]:
                    config_dir = cfg_dir
                    break

        for imp in f.imports:
            if imp.is_dynamic_unresolved:
                edges.append(ResolvedEdge(module, "<dynamic>", EdgeKind.UNRESOLVED, raw="import(<non-literal>)"))
                continue
            if imp.is_export_forward:
                continue  # already folded into the barrel index; not a graph edge itself

            specifier = imp.module
            if not specifier:
                continue

            if specifier.startswith("."):
                resolved = _resolve_relative(specifier, importer_path)
                if resolved is None:
                    edges.append(ResolvedEdge(module, specifier, EdgeKind.UNRESOLVED, raw=specifier))
                    continue
                if resolved.suffix not in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
                    edges.append(ResolvedEdge(module, resolved.name, EdgeKind.EXTERNAL, raw=specifier))
                    continue
                target_module = _module_name_for(resolved, root)
                if target_module not in module_to_path:
                    edges.append(ResolvedEdge(module, specifier, EdgeKind.UNRESOLVED, raw=specifier))
                    continue

                if imp.is_star or not imp.names:
                    edges.append(ResolvedEdge(module, target_module, EdgeKind.INTERNAL, raw=specifier))
                    continue
                for name in imp.names:
                    found = _resolve_named(target_module, name, _MAX_STAR_HOPS)
                    edges.append(
                        ResolvedEdge(module, found or target_module, EdgeKind.INTERNAL, raw=f"{specifier}::{name}")
                    )
                continue

            # Bare specifier: try tsconfig paths/baseUrl, else assume external.
            resolved = _resolve_via_tsconfig(specifier, config, config_dir) if config else None
            if resolved is not None:
                target_module = _module_name_for(resolved, root)
                if target_module in module_to_path:
                    edges.append(ResolvedEdge(module, target_module, EdgeKind.INTERNAL, raw=specifier))
                    continue
            edges.append(ResolvedEdge(module, _external_package_name(specifier), EdgeKind.EXTERNAL, raw=specifier))

    # Convert to repo-relative paths only now — every resolution step
    # above needs absolute filesystem paths to join against a specifier's
    # directory. An absolute path only makes sense inside the ephemeral
    # clone dir it came from, and leaks local filesystem detail (e.g.
    # into committed demo reports).
    for f in parsed:
        f.path = Path(f.path).relative_to(root).as_posix()

    return ResolutionResult(files=parsed, edges=edges)
