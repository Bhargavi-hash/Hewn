from __future__ import annotations

from hewn.repository.index import RepositoryIndex

from .models import RepositoryDocument


def build_symbol_documents(
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

        for symbol in source_file.symbols:
            lines = [
                f"path: {path}",
                f"symbol: {symbol.qualified_name}",
                f"kind: {symbol.kind.value}",
            ]

            if symbol.signature is not None:
                lines.append(
                    f"signature: {symbol.signature}"
                )

            documents.append(
                RepositoryDocument(
                    path=path,
                    symbol=symbol.qualified_name,
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