from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from hewn.repository.models import FileDependency, SourceFile, Symbol
from hewn.repository.python_parser import (
    PythonParseError,
    parse_python_source,
)

_IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
    }
)


def _should_index(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)

    return not any(
        part in _IGNORED_DIRECTORY_NAMES
        for part in relative.parts
    )


def _module_path_map(
    files: dict[PurePosixPath, SourceFile],
) -> dict[str, PurePosixPath]:
    result: dict[str, PurePosixPath] = {}

    for path in files:
        if path.suffix != ".py":
            continue

        parts = list(path.with_suffix("").parts)

        # Convert:
        # src/hewn/tools.py -> hewn.tools
        if parts and parts[0] == "src":
            parts = parts[1:]

        # Convert:
        # src/hewn/__init__.py -> hewn
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        if parts:
            result[".".join(parts)] = path

    return result


def _resolve_import(
    *,
    module: str,
    module_paths: dict[str, PurePosixPath],
) -> PurePosixPath | None:
    # Relative imports will be handled separately later.
    if not module or module.startswith("."):
        return None

    candidate = module

    while candidate:
        target = module_paths.get(candidate)

        if target is not None:
            return target

        if "." not in candidate:
            break

        candidate = candidate.rsplit(".", 1)[0]

    return None


def _build_internal_dependencies(
    files: dict[PurePosixPath, SourceFile],
) -> tuple[FileDependency, ...]:
    module_paths = _module_path_map(files)
    dependencies: set[FileDependency] = set()

    for source_path, source_file in files.items():
        for imported in source_file.imports:
            target = _resolve_import(
                module=imported.module,
                module_paths=module_paths,
            )

            if target is None or target == source_path:
                continue

            dependencies.add(
                FileDependency(
                    source=source_path,
                    target=target,
                )
            )

    return tuple(
        sorted(
            dependencies,
            key=lambda dependency: (
                str(dependency.source),
                str(dependency.target),
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class RepositoryIndex:
    files: dict[PurePosixPath, SourceFile]
    symbols_by_name: dict[str, tuple[Symbol, ...]]
    symbols_by_qualified_name: dict[str, tuple[Symbol, ...]]
    dependencies: tuple[FileDependency, ...]

    @classmethod
    def build(cls, root: Path) -> RepositoryIndex:
        files: dict[PurePosixPath, SourceFile] = {}
        symbols_by_name: defaultdict[str, list[Symbol]] = defaultdict(list)
        symbols_by_qualified_name: defaultdict[str, list[Symbol]] = defaultdict(list)

        # Phase 1: discover and parse repository files.
        for path in sorted(root.rglob("*.py")):
            if not path.is_file() or not _should_index(path, root):
                continue

            relative_path = PurePosixPath(
                path.relative_to(root).as_posix()
            )

            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            try:
                source_file = parse_python_source(
                    relative_path,
                    source,
                )
            except PythonParseError:
                continue

            files[relative_path] = source_file

            for symbol in source_file.symbols:
                symbols_by_name[symbol.name].append(symbol)
                symbols_by_qualified_name[
                    symbol.qualified_name
                ].append(symbol)

        # Phase 2: resolve relationships after all files are known.
        dependencies = _build_internal_dependencies(files)

        return cls(
            files=files,
            symbols_by_name={
                name: tuple(symbols)
                for name, symbols in symbols_by_name.items()
            },
            symbols_by_qualified_name={
                name: tuple(symbols)
                for name, symbols in symbols_by_qualified_name.items()
            },
            dependencies=dependencies,
        )

    def find_symbol(
        self,
        name: str,
    ) -> tuple[Symbol, ...]:
        return self.symbols_by_name.get(name, ())

    def find_qualified_symbol(
        self,
        qualified_name: str,
    ) -> tuple[Symbol, ...]:
        return self.symbols_by_qualified_name.get(
            qualified_name,
            (),
        )

    def get_file(
        self,
        path: PurePosixPath,
    ) -> SourceFile | None:
        return self.files.get(path)

    def dependencies_from(
        self,
        path: PurePosixPath,
    ) -> tuple[FileDependency, ...]:
        return tuple(
            dependency
            for dependency in self.dependencies
            if dependency.source == path
        )

    def dependents_of(
        self,
        path: PurePosixPath,
    ) -> tuple[FileDependency, ...]:
        return tuple(
            dependency
            for dependency in self.dependencies
            if dependency.target == path
        )