"""Resolve raw Python imports into real file edges.

Never imports or executes target code — everything here is static: a
module index built from file paths, plus a small re-export alias table
for `__init__.py` forwarding. This is the correctness foundation of the
whole pipeline; a wrong edge here poisons every later stage.
"""

from __future__ import annotations

import sys
from pathlib import Path

from cartograph.ingest.discover import discover_python_files
from cartograph.models import EdgeKind, ParsedFile, RawImport, ResolutionResult, ResolvedEdge
from cartograph.parse.python import parse_python_file

_STDLIB = set(getattr(sys, "stdlib_module_names", ()))


def detect_source_roots(root: Path) -> list[Path]:
    """Find the directory/directories module names should be computed relative to.

    Handles the common src-layout vs flat-layout split. Does not parse
    pyproject.toml package-dir remaps yet — documented MVP limitation,
    tracked as a source of resolution error alongside the unresolved %.
    """
    src_dir = root / "src"
    if src_dir.is_dir():
        candidates = [p for p in src_dir.iterdir() if p.is_dir() and (p / "__init__.py").exists()]
        if candidates:
            return [src_dir]
    return [root]


def _module_name_for(path: Path, source_roots: list[Path]) -> str:
    best_root = max(
        (r for r in source_roots if _is_relative_to(path, r)),
        key=lambda r: len(r.parts),
        default=None,
    )
    if best_root is None:
        return path.stem
    rel = path.relative_to(best_root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _anchor_package(module_name: str, is_package: bool) -> str:
    if is_package:
        return module_name
    return module_name.rsplit(".", 1)[0] if "." in module_name else ""


def _resolve_relative(anchor: str, level: int, extra: str) -> str:
    parts = anchor.split(".") if anchor else []
    up = level - 1
    if up > 0:
        parts = parts[:-up] if up <= len(parts) else []
    base = ".".join(parts)
    if extra:
        return f"{base}.{extra}" if base else extra
    return base


def _longest_prefix_match(target: str, module_to_path: dict[str, str]) -> str | None:
    parts = target.split(".")
    for cut in range(len(parts), 0, -1):
        candidate = ".".join(parts[:cut])
        if candidate in module_to_path:
            return candidate
    return None


def _build_reexport_aliases(
    files_by_module: dict[str, ParsedFile], module_to_path: dict[str, str]
) -> dict[str, str]:
    """Map `pkg.Y` -> the module that actually defines Y, for `__init__.py` forwarding."""
    aliases: dict[str, str] = {}
    for module_name, f in files_by_module.items():
        if Path(f.path).name != "__init__.py":
            continue
        anchor = module_name
        for imp in f.imports:
            if imp.is_star or not imp.names:
                continue
            target = _resolve_relative(anchor, imp.level, imp.module) if imp.level > 0 else imp.module
            resolved_target = _longest_prefix_match(target, module_to_path) or (
                target if target in module_to_path else None
            )
            if resolved_target is None:
                continue
            for name in imp.names:
                candidate_module = f"{resolved_target}.{name}"
                defining = candidate_module if candidate_module in module_to_path else resolved_target
                aliases[f"{module_name}.{name}"] = defining
    return aliases


def _classify_absolute(target: str, module_to_path: dict[str, str]) -> tuple[EdgeKind, str]:
    resolved = _longest_prefix_match(target, module_to_path)
    if resolved is not None:
        return EdgeKind.INTERNAL, resolved
    top = target.split(".")[0]
    if top in _STDLIB or top == "":
        return EdgeKind.EXTERNAL, target
    # Not stdlib and not found in the repo's own module index: assume
    # third-party rather than unresolved. Ambiguous by construction; the
    # unresolved-% metric is what surfaces genuine resolution failures.
    return EdgeKind.EXTERNAL, target


def _resolve_import(
    imp: RawImport,
    anchor: str,
    module_to_path: dict[str, str],
    aliases: dict[str, str],
) -> list[ResolvedEdge]:
    edges: list[ResolvedEdge] = []

    if imp.level > 0:
        target = _resolve_relative(anchor, imp.level, imp.module)

        if imp.is_star:
            if target in module_to_path:
                edges.append(ResolvedEdge("", target, EdgeKind.INTERNAL, raw=f"{'.' * imp.level}{imp.module}"))
            else:
                edges.append(ResolvedEdge("", target, EdgeKind.UNRESOLVED, raw=f"{'.' * imp.level}{imp.module}"))
            return edges

        if not imp.names:
            # `from . import` with no names is malformed; nothing to resolve.
            return edges

        for name in imp.names:
            candidate = f"{target}.{name}" if target else name
            if candidate in module_to_path:
                edges.append(ResolvedEdge("", candidate, EdgeKind.INTERNAL, raw=candidate))
            elif target in module_to_path:
                edges.append(ResolvedEdge("", target, EdgeKind.INTERNAL, raw=candidate))
            elif candidate in aliases:
                edges.append(ResolvedEdge("", aliases[candidate], EdgeKind.INTERNAL, raw=candidate))
            else:
                edges.append(ResolvedEdge("", candidate, EdgeKind.UNRESOLVED, raw=candidate))
        return edges

    if imp.is_star:
        kind, dst = _classify_absolute(imp.module, module_to_path)
        edges.append(ResolvedEdge("", dst, kind, raw=imp.module))
        return edges

    kind, dst = _classify_absolute(imp.module, module_to_path)
    edges.append(ResolvedEdge("", dst, kind, raw=imp.module))
    return edges


def resolve_python_repo(root: Path) -> ResolutionResult:
    paths = discover_python_files(root)
    parsed = [parse_python_file(p) for p in paths]

    source_roots = detect_source_roots(root)
    for f in parsed:
        f.module_name = _module_name_for(Path(f.path), source_roots)

    module_to_path = {f.module_name: f.path for f in parsed}
    files_by_module = {f.module_name: f for f in parsed}
    aliases = _build_reexport_aliases(files_by_module, module_to_path)

    edges: list[ResolvedEdge] = []
    for f in parsed:
        is_package = Path(f.path).name == "__init__.py"
        anchor = _anchor_package(f.module_name, is_package)
        for imp in f.imports:
            for edge in _resolve_import(imp, anchor, module_to_path, aliases):
                edge.src = f.module_name
                edges.append(edge)

    return ResolutionResult(files=parsed, edges=edges)
