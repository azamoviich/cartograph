"""Shared data structures passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ImportKind(str, Enum):
    RELATIVE = "relative"
    ABSOLUTE = "absolute"
    STAR = "star"
    DYNAMIC = "dynamic"


@dataclass
class RawImport:
    """One import statement as seen in source, before resolution."""

    module: str  # dotted module path as written, e.g. "..a.b" or "pkg.mod"
    names: list[str] = field(default_factory=list)  # imported symbols, [] for `import x`
    level: int = 0  # relative-import dot count; 0 = absolute
    line: int = 0
    is_star: bool = False
    type_checking: bool = False  # guarded by `if TYPE_CHECKING:` — excluded from cycle detection


@dataclass
class ParsedFile:
    """Output of the parse stage for one source file."""

    path: str  # repo-relative path
    module_name: str = ""  # dotted module name, filled in by the resolve stage
    imports: list[RawImport] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)  # top-level def/class names
    docstring: str | None = None
    loc: int = 0


class EdgeKind(str, Enum):
    INTERNAL = "internal"  # resolved to a file in this repo
    EXTERNAL = "external"  # third-party or stdlib
    UNRESOLVED = "unresolved"  # could not be resolved


@dataclass
class ResolvedEdge:
    src: str  # module_name of importing file
    dst: str  # module_name of imported file, or the raw external/unresolved name
    kind: EdgeKind
    raw: str = ""  # original import string, kept for debugging
    type_checking: bool = False  # forwarded from RawImport; excluded from cycle detection


@dataclass
class ResolutionResult:
    files: list[ParsedFile]
    edges: list[ResolvedEdge]

    @property
    def unresolved_ratio(self) -> float:
        if not self.edges:
            return 0.0
        unresolved = sum(1 for e in self.edges if e.kind is EdgeKind.UNRESOLVED)
        return unresolved / len(self.edges)
