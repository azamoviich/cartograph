"""Tree-sitter based parsing of a single JS/TS/JSX/TSX file.

Syntax only, same contract as parse/python.py: extract raw import
specifiers, `export ... from` barrel-forwarding statements, top-level
symbol names, and a leading comment as a docstring substitute. Turning
specifiers into real file edges is resolve/javascript.py's job.

Only literal string specifiers are followed. `require(x)` with a
variable, or `import(\\`...${{x}}...\\`)` with a template literal, are
recorded as unresolved rather than guessed — the resolver has nothing
static to go on.
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from cartograph.models import ParsedFile, RawImport

_JS_LANGUAGE = Language(tsjs.language())
_TS_LANGUAGE = Language(tsts.language_typescript())
_TSX_LANGUAGE = Language(tsts.language_tsx())

_JS_PARSER = Parser(_JS_LANGUAGE)
_TS_PARSER = Parser(_TS_LANGUAGE)
_TSX_PARSER = Parser(_TSX_LANGUAGE)


def _parser_for(path: Path) -> Parser:
    suffix = path.suffix
    if suffix == ".tsx":
        return _TSX_PARSER
    if suffix == ".ts":
        return _TS_PARSER
    return _JS_PARSER


def _text(node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _string_literal_value(node, source: bytes) -> str | None:
    """Return the literal contents of a `string` node, or None if it isn't one."""
    if node is None or node.type != "string":
        return None
    for child in node.children:
        if child.type == "string_fragment":
            return _text(child, source)
    return ""  # empty string literal


def _named_import_names(clause_node, source: bytes) -> tuple[list[str], bool]:
    """Returns (imported local names, has_namespace_import)."""
    names: list[str] = []
    has_namespace = False
    for child in clause_node.children:
        if child.type == "identifier":
            names.append(_text(child, source))  # default import
        elif child.type == "namespace_import":
            has_namespace = True
        elif child.type == "named_imports":
            for spec in child.children:
                if spec.type != "import_specifier":
                    continue
                idents = [c for c in spec.children if c.type == "identifier"]
                # `useEffect as fx`: two identifiers, want the original (imported) name.
                names.append(_text(idents[0], source) if idents else "")
    return names, has_namespace


def _parse_import_statement(node, source: bytes) -> RawImport | None:
    string_node = next((c for c in node.children if c.type == "string"), None)
    specifier = _string_literal_value(string_node, source)
    if specifier is None:
        return None

    clause = next((c for c in node.children if c.type == "import_clause"), None)
    names: list[str] = []
    is_star = False
    if clause is not None:
        names, is_star = _named_import_names(clause, source)

    return RawImport(module=specifier, names=names, is_star=is_star)


def _parse_export_statement(node, source: bytes) -> tuple[RawImport | None, list[str]]:
    """Returns (forwarding RawImport if `export ... from`, else None; local export names)."""
    string_node = next((c for c in node.children if c.type == "string"), None)
    local_names: list[str] = []

    if string_node is not None:
        specifier = _string_literal_value(string_node, source)
        has_star = any(c.type == "*" for c in node.children)
        names: list[str] = []
        for child in node.children:
            if child.type == "export_clause":
                for spec in child.children:
                    if spec.type != "export_specifier":
                        continue
                    idents = [c for c in spec.children if c.type == "identifier"]
                    if idents:
                        names.append(_text(idents[0], source))  # original name, before `as`
        return RawImport(module=specifier or "", names=names, is_star=has_star, is_export_forward=True), []

    for child in node.children:
        if child.type == "export_clause":
            for spec in child.children:
                if spec.type != "export_specifier":
                    continue
                idents = [c for c in spec.children if c.type == "identifier"]
                if idents:
                    local_names.append(_text(idents[-1], source))  # exported (possibly aliased) name
        elif child.type in ("function_declaration", "class_declaration", "generator_function_declaration"):
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                local_names.append(_text(name_node, source))
        elif child.type == "lexical_declaration" or child.type == "variable_declaration":
            for decl in child.children:
                if decl.type == "variable_declarator":
                    name_node = decl.child_by_field_name("name")
                    if name_node is not None and name_node.type == "identifier":
                        local_names.append(_text(name_node, source))

    return None, local_names


def _call_target_name(call_node, source: bytes) -> str | None:
    func = call_node.child_by_field_name("function")
    if func is None:
        return None
    if func.type == "identifier":
        return _text(func, source)
    if func.type == "import":  # dynamic import()
        return "import"
    return None


def _parse_call_expression(node, source: bytes) -> RawImport | None:
    target = _call_target_name(node, source)
    if target not in ("require", "import"):
        return None

    args = node.child_by_field_name("arguments")
    if args is None:
        return None
    arg_nodes = [c for c in args.children if c.type not in ("(", ")", ",")]
    if not arg_nodes:
        return None

    specifier = _string_literal_value(arg_nodes[0], source)
    if specifier is None:
        # Non-literal specifier (variable, template literal): a real
        # dependency we can't follow. Record it rather than silently
        # dropping it, so it surfaces in the unresolved-% metric.
        return RawImport(module="", is_dynamic_unresolved=True)
    return RawImport(module=specifier)


def _collect_top_level_symbols(root, source: bytes) -> list[str]:
    symbols = []

    def declared_name(node) -> str | None:
        if node.type in ("function_declaration", "class_declaration", "generator_function_declaration"):
            name_node = node.child_by_field_name("name")
            return _text(name_node, source) if name_node is not None else None
        return None

    for child in root.children:
        name = declared_name(child)
        if name:
            symbols.append(name)
        elif child.type == "export_statement":
            for grandchild in child.children:
                name = declared_name(grandchild)
                if name:
                    symbols.append(name)
                elif grandchild.type in ("lexical_declaration", "variable_declaration"):
                    for decl in grandchild.children:
                        if decl.type == "variable_declarator":
                            name_node = decl.child_by_field_name("name")
                            if name_node is not None and name_node.type == "identifier":
                                symbols.append(_text(name_node, source))
    return symbols


def _leading_comment(root, source: bytes) -> str | None:
    if not root.children or root.children[0].type != "comment":
        return None
    text = _text(root.children[0], source)
    return text.strip("/* \t").strip()[:200] or None


def parse_javascript_file(path: Path) -> ParsedFile:
    source = path.read_bytes()
    parser = _parser_for(path)
    tree = parser.parse(source)
    root = tree.root_node

    imports: list[RawImport] = []

    def walk(node) -> None:
        if node.type == "import_statement":
            parsed = _parse_import_statement(node, source)
            if parsed is not None:
                imports.append(parsed)
            return
        if node.type == "export_statement":
            forward, _local_names = _parse_export_statement(node, source)
            if forward is not None:
                imports.append(forward)
            for child in node.children:
                walk(child)
            return
        if node.type == "call_expression":
            call_import = _parse_call_expression(node, source)
            if call_import is not None:
                imports.append(call_import)
        for child in node.children:
            walk(child)

    walk(root)

    return ParsedFile(
        path=str(path),
        imports=imports,
        symbols=_collect_top_level_symbols(root, source),
        docstring=_leading_comment(root, source),
        loc=source.count(b"\n") + 1,
    )
