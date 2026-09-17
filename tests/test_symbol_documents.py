from pathlib import Path, PurePosixPath

from hewn.repository.index import RepositoryIndex
from hewn.retrieval.symbol_documents import (
    build_symbol_documents,
)


def test_builds_one_document_per_symbol(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "tools.py").write_text(
        (
            "class ToolExecutor:\n"
            "    def execute("
            "self, call: ToolCall"
            ") -> ToolResult:\n"
            "        raise NotImplementedError\n"
        ),
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    documents = build_symbol_documents(
        index,
        path_prefix="src",
    )

    assert len(documents) == 2

    assert [
        document.symbol
        for document in documents
    ] == [
        "ToolExecutor",
        "ToolExecutor.execute",
    ]


def test_symbol_document_preserves_source_path(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "workspace.py").write_text(
        (
            "class Workspace:\n"
            "    def resolve("
            "self, path: str"
            ") -> Path:\n"
            "        raise NotImplementedError\n"
        ),
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    documents = build_symbol_documents(
        index,
        path_prefix="src",
    )

    assert all(
        document.path
        == PurePosixPath(
            "src/example/workspace.py"
        )
        for document in documents
    )


def test_symbol_document_contains_signature(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "tools.py").write_text(
        (
            "class ToolExecutor:\n"
            "    def execute("
            "self, call: ToolCall"
            ") -> ToolResult:\n"
            "        raise NotImplementedError\n"
        ),
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    documents = build_symbol_documents(
        index,
        path_prefix="src",
    )

    method_document = next(
        document
        for document in documents
        if document.symbol
        == "ToolExecutor.execute"
    )

    assert (
        "signature: "
        "execute(self, call: ToolCall) -> ToolResult"
        in method_document.text
    )


def test_class_document_has_no_signature(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "workspace.py").write_text(
        "class Workspace:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    documents = build_symbol_documents(
        index,
        path_prefix="src",
    )

    assert len(documents) == 1
    assert documents[0].symbol == "Workspace"
    assert "signature:" not in documents[0].text


def test_symbol_documents_can_be_scoped(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    tests = tmp_path / "tests"

    src.mkdir()
    tests.mkdir()

    (src / "app.py").write_text(
        "class Application:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (tests / "test_app.py").write_text(
        "def test_application():\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    documents = build_symbol_documents(
        index,
        path_prefix="src",
    )

    assert len(documents) == 1
    assert documents[0].symbol == "Application"