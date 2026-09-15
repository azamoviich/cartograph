"""Tree-sitter based parsing of a single Python file.

Syntax only: extracts raw import statements, top-level symbol names, the
module docstring, and line count. Turning import strings into real file
edges is the resolve stage's job, not this one.
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from cartograph.models import ParsedFile, RawImport

_LANGUAGE = Language(tspython.language())
_PARSER = Parser(_LANGUAGE)


def _text(node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _dotted_name(node, source: bytes) -> str:
    """Render a dotted_name / attribute chain node back to 'a.b.c'."""
    return _text(node, source).replace(" ", "")


def _parse_import_statement(node, source: bytes) -> list[RawImport]:
    """`import a.b`, `import a.b as c`, `import a, b`"""
    imports = []
    for child in node.children:
        if child.type == "dotted_name":
            imports.append(RawImport(module=_dotted_name(child, source)))
        elif child.type == "aliased_import":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                imports.append(RawImport(module=_dotted_name(name_node, source)))
    return imports


def _parse_import_from_statement(node, source: bytes, line: int) -> RawImport | None:
    """`from .a.b import c, d`, `from a.b import *`, `from ..a import b as c`"""
    level = 0
    module_parts: list[str] = []
    names: list[str] = []
    is_star = False

    # The grammar assigns the `module_name` field to either a plain
    # dotted_name (absolute import) or a relative_import node (relative
    # import, itself wrapping an optional import_prefix + dotted_name).
    # Do not also scan for these node types elsewhere in node.children —
    # that double-counts the same node and duplicates module segments.
    module_node = node.child_by_field_name("module_name")
    if module_node is not None:
        if module_node.type == "relative_import":
            for c in module_node.children:
                if c.type == "import_prefix":
                    level += _text(c, source).count(".")
                elif c.type == "dotted_name":
                    module_parts.append(_dotted_name(c, source))
        else:
            module_parts.append(_dotted_name(module_node, source))
    else:
        # No module_name field at all: bare `from . import x` has only an
        # import_prefix child for the dots.
        for c in node.children:
            if c.type == "import_prefix":
                level += _text(c, source).count(".")

    for child in node.children:
        if child.type == "wildcard_import":
            is_star = True
        elif child.type == "aliased_import":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                names.append(_text(name_node, source))
        elif child.type == "dotted_name" and child != module_node:
            names.append(_text(child, source))
        elif child.type == "identifier" and child != module_node:
            names.append(_text(child, source))

    if level == 0 and not module_parts:
        return None

    return RawImport(
        module=".".join(module_parts),
        names=names,
        level=level,
        line=line,
        is_star=is_star,
    )


def _collect_symbols(tree_root, source: bytes) -> list[str]:
    symbols = []
    for child in tree_root.children:
        if child.type in ("function_definition", "class_definition"):
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                symbols.append(_text(name_node, source))
        elif child.type == "decorated_definition":
            inner = child.child_by_field_name("definition")
            if inner is not None:
                name_node = inner.child_by_field_name("name")
                if name_node is not None:
                    symbols.append(_text(name_node, source))
    return symbols


def _module_docstring(tree_root, source: bytes) -> str | None:
    if not tree_root.children:
        return None
    first = tree_root.children[0]
    if first.type == "expression_statement" and first.children and first.children[0].type == "string":
        raw = _text(first.children[0], source)
        return raw.strip("\"'").strip() or None
    return None


def parse_python_file(path: Path) -> ParsedFile:
    source = path.read_bytes()
    tree = _PARSER.parse(source)
    root = tree.root_node

    imports: list[RawImport] = []

    def walk(node, depth: int) -> None:
        # Only descend into module-level and function/class bodies enough to
        # find imports; we don't need full-body traversal for MVP, but
        # imports guarded by `if TYPE_CHECKING:` or nested in functions are
        # still real edges, so we walk the whole tree.
        if node.type == "import_statement":
            imports.extend(_parse_import_statement(node, source))
        elif node.type == "import_from_statement":
            parsed = _parse_import_from_statement(node, source, node.start_point[0] + 1)
            if parsed is not None:
                imports.append(parsed)
        for child in node.children:
            walk(child, depth + 1)

    walk(root, 0)

    return ParsedFile(
        path=str(path),
        imports=imports,
        symbols=_collect_symbols(root, source),
        docstring=_module_docstring(root, source),
        loc=source.count(b"\n") + 1,
    )
