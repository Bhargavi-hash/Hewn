from __future__ import annotations

import ast
from pathlib import PurePosixPath

from hewn.repository.models import (
    Import,
    SourceFile,
    SourceLocation,
    Symbol,
    SymbolKind,
)


class PythonParseError(ValueError):
    """Raised when Python source cannot be parsed."""


def parse_python_source(
    path: PurePosixPath,
    source: str,
) -> SourceFile:
    try:
        tree = ast.parse(
            source,
            filename=str(path),
        )
    except SyntaxError as exc:
        raise PythonParseError(
            f"Could not parse Python source: {path}"
        ) from exc

    symbols: list[Symbol] = []
    imports: list[Import] = []

    _collect_statements(
        tree.body,
        path=path,
        symbols=symbols,
        imports=imports,
        parent_symbol=None,
    )

    return SourceFile(
        path=path,
        language="python",
        symbols=tuple(symbols),
        imports=tuple(imports),
    )


def _collect_statements(
    statements: list[ast.stmt],
    *,
    path: PurePosixPath,
    symbols: list[Symbol],
    imports: list[Import],
    parent_symbol: str | None,
) -> None:
    for statement in statements:
        if isinstance(statement, ast.ClassDef):
            qualified_name = _qualified_name(
                parent_symbol,
                statement.name,
            )

            symbols.append(
                Symbol(
                    name=statement.name,
                    kind=SymbolKind.CLASS,
                    qualified_name=qualified_name,
                    location=_location(
                        path,
                        statement,
                    ),
                )
            )

            _collect_statements(
                statement.body,
                path=path,
                symbols=symbols,
                imports=imports,
                parent_symbol=qualified_name,
            )

        elif isinstance(
            statement,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            qualified_name = _qualified_name(
                parent_symbol,
                statement.name,
            )

            kind = (
                SymbolKind.METHOD
                if parent_symbol is not None
                else SymbolKind.FUNCTION
            )

            symbols.append(
                Symbol(
                    name=statement.name,
                    kind=kind,
                    qualified_name=qualified_name,
                    signature=_function_signature(
                        statement
                    ),
                    location=_location(
                        path,
                        statement,
                    ),
                )
            )

        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                imports.append(
                    Import(
                        module=alias.name,
                        name=None,
                        alias=alias.asname,
                        location=_location(
                            path,
                            statement,
                        ),
                    )
                )

        elif isinstance(statement, ast.ImportFrom):
            module = (
                "." * statement.level
                + (statement.module or "")
            )

            for alias in statement.names:
                imports.append(
                    Import(
                        module=module,
                        name=alias.name,
                        alias=alias.asname,
                        location=_location(
                            path,
                            statement,
                        ),
                    )
                )


def _function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    arguments = ast.unparse(node.args)

    signature = (
        f"{node.name}({arguments})"
    )

    if node.returns is not None:
        signature += (
            f" -> {ast.unparse(node.returns)}"
        )

    return signature


def _qualified_name(
    parent: str | None,
    name: str,
) -> str:
    if parent is None:
        return name

    return f"{parent}.{name}"


def _location(
    path: PurePosixPath,
    node: ast.AST,
) -> SourceLocation:
    start_line = getattr(
        node,
        "lineno",
        None,
    )
    end_line = getattr(
        node,
        "end_lineno",
        None,
    )

    if start_line is None:
        raise PythonParseError(
            f"AST node has no source location: {path}"
        )

    return SourceLocation(
        path=path,
        start_line=start_line,
        end_line=end_line or start_line,
    )