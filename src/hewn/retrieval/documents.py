from __future__ import annotations

from hewn.repository.index import RepositoryIndex

from .models import RepositoryDocument


def build_repository_documents(
    repository_index: RepositoryIndex,
    *,
    path_prefix: str | None = None,
) -> tuple[RepositoryDocument, ...]:
    documents: list[RepositoryDocument] = []

    for path, source_file in sorted(
        repository_index.files.items(),
        key=lambda item: str(item[0]),
    ):
        path_text = str(path)

        if (
            path_prefix is not None
            and not _matches_prefix(
                path_text,
                path_prefix,
            )
        ):
            continue

        lines = [
            f"path: {path}",
        ]

        if source_file.symbols:
            lines.append("symbols:")

            for symbol in source_file.symbols:
                symbol_line = (
                    f"  {symbol.kind.value}: "
                    f"{symbol.qualified_name}"
                )

                if symbol.signature is not None:
                    symbol_line += (
                        f" | signature: "
                        f"{symbol.signature}"
                    )

                lines.append(symbol_line)

        dependencies = (
            repository_index.dependencies_from(
                path
            )
        )

        if dependencies:
            lines.append("imports:")

            for dependency in dependencies:
                lines.append(
                    f"  {dependency.target}"
                )

        documents.append(
            RepositoryDocument(
                path=path,
                text="\n".join(lines),
            )
        )

    return tuple(documents)


def _matches_prefix(
    path: str,
    prefix: str,
) -> bool:
    normalized_prefix = prefix.rstrip("/")

    return (
        path == normalized_prefix
        or path.startswith(
            normalized_prefix + "/"
        )
    )