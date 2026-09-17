from pathlib import Path, PurePosixPath

import pytest

from hewn.repository.index import RepositoryIndex
from hewn.retrieval.documents import build_repository_documents
from hewn.retrieval.models import RepositoryDocument


def test_repository_document_rejects_absolute_path() -> None:
    with pytest.raises(ValueError):
        RepositoryDocument(
            path=PurePosixPath("/src/hewn/agent.py"),
            text="Agent",
        )


def test_repository_document_rejects_parent_traversal() -> None:
    with pytest.raises(ValueError):
        RepositoryDocument(
            path=PurePosixPath("../agent.py"),
            text="Agent",
        )


def test_repository_document_rejects_empty_text() -> None:
    with pytest.raises(ValueError):
        RepositoryDocument(
            path=PurePosixPath("agent.py"),
            text="   ",
        )


def test_build_repository_documents_contains_structure(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "worker.py").write_text(
        "class Worker:\n"
        "    def run(self) -> None:\n"
        "        pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    documents = build_repository_documents(
        index,
        path_prefix="src",
    )

    assert len(documents) == 1

    document = documents[0]

    assert document.path == PurePosixPath(
        "src/example/worker.py"
    )
    assert "Worker" in document.text
    assert "Worker.run" in document.text


def test_build_repository_documents_can_scope_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src"
    tests = tmp_path / "tests"

    source.mkdir()
    tests.mkdir()

    (source / "agent.py").write_text(
        "class Agent:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (tests / "test_agent.py").write_text(
        "def test_agent() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    documents = build_repository_documents(
        index,
        path_prefix="src",
    )

    paths = {
        str(document.path)
        for document in documents
    }

    assert "src/agent.py" in paths
    assert "tests/test_agent.py" not in paths

def test_repository_document_contains_function_signatures(
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

    documents = build_repository_documents(
        index,
        path_prefix="src",
    )

    assert len(documents) == 1

    text = documents[0].text

    assert "ToolExecutor.execute" in text
    assert (
        "execute(self, call: ToolCall) -> ToolResult"
        in text
    )