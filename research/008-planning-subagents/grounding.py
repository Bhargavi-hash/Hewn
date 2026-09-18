from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class FileStructure:
    path: str
    symbols: tuple[str, ...]
    imports: tuple[str, ...]


def _import_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return ", ".join(
            alias.name for alias in node.names
        )

    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        names = ", ".join(
            alias.name for alias in node.names
        )
        return f"{module}: {names}"

    return None


def extract_structure(
    files: dict[str, str],
) -> tuple[FileStructure, ...]:
    structures: list[FileStructure] = []

    for path in sorted(files):
        source = files[path]

        if not path.endswith(".py"):
            structures.append(
                FileStructure(
                    path=path,
                    symbols=(),
                    imports=(),
                )
            )
            continue

        tree = ast.parse(source)

        symbols: list[str] = []
        imports: list[str] = []

        for node in tree.body:
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                symbols.append(node.name)
            elif isinstance(
                node,
                (ast.Assign, ast.AnnAssign),
            ):
                targets: list[ast.expr]

                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                else:
                    targets = [node.target]

                for target in targets:
                    if isinstance(target, ast.Name):
                        symbols.append(target.id)

            import_name = _import_name(node)
            if import_name is not None:
                imports.append(import_name)

        structures.append(
            FileStructure(
                path=path,
                symbols=tuple(symbols),
                imports=tuple(imports),
            )
        )

    return tuple(structures)


def format_structure(
    structures: tuple[FileStructure, ...],
) -> str:
    lines = ["Repository structure:"]

    for structure in structures:
        lines.append(f"- {structure.path}")

        if structure.symbols:
            lines.append(
                "  symbols: "
                + ", ".join(structure.symbols)
            )

        if structure.imports:
            lines.append(
                "  imports: "
                + " | ".join(structure.imports)
            )

    return "\n".join(lines)