from pathlib import Path, PurePosixPath

from hewn.repository.index import RepositoryIndex
from hewn.repository.models import FileDependency, SymbolKind


def test_repository_index_builds_source_files(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "agent.py").write_text(
        "class Agent:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    path = PurePosixPath("src/example/agent.py")

    assert path in index.files
    assert index.files[path].language == "python"


def test_repository_index_finds_symbol_by_name(
    tmp_path: Path,
) -> None:
    (tmp_path / "tools.py").write_text(
        "class ToolExecutor:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    matches = index.find_symbol("ToolExecutor")

    assert len(matches) == 1
    assert matches[0].name == "ToolExecutor"
    assert matches[0].kind is SymbolKind.CLASS
    assert matches[0].location.path == PurePosixPath("tools.py")


def test_repository_index_preserves_duplicate_symbol_names(
    tmp_path: Path,
) -> None:
    (tmp_path / "first.py").write_text(
        "def run() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (tmp_path / "second.py").write_text(
        "def run() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    matches = index.find_symbol("run")

    assert len(matches) == 2
    assert {
        match.location.path
        for match in matches
    } == {
        PurePosixPath("first.py"),
        PurePosixPath("second.py"),
    }


def test_repository_index_finds_qualified_method(
    tmp_path: Path,
) -> None:
    (tmp_path / "agents.py").write_text(
        "class Agent:\n"
        "    def run(self) -> None:\n"
        "        pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    matches = index.find_qualified_symbol("Agent.run")

    assert len(matches) == 1
    assert matches[0].kind is SymbolKind.METHOD


def test_repository_index_returns_empty_for_unknown_symbol(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "class Existing:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    assert index.find_symbol("Missing") == ()
    assert index.find_qualified_symbol("Missing.run") == ()


def test_repository_index_gets_file(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "def example() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    source_file = index.get_file(
        PurePosixPath("example.py")
    )

    assert source_file is not None
    assert source_file.path == PurePosixPath("example.py")


def test_repository_index_skips_invalid_python(
    tmp_path: Path,
) -> None:
    (tmp_path / "broken.py").write_text(
        "def broken(\n",
        encoding="utf-8",
    )

    (tmp_path / "valid.py").write_text(
        "class Valid:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    assert PurePosixPath("broken.py") not in index.files
    assert PurePosixPath("valid.py") in index.files
    assert len(index.find_symbol("Valid")) == 1

def test_repository_index_ignores_dependency_and_cache_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "real.py").write_text(
        "class RealSymbol:\n"
        "    pass\n",
        encoding="utf-8",
    )

    ignored_files = [
        tmp_path / ".venv" / "dependency.py",
        tmp_path / "__pycache__" / "cached.py",
        tmp_path / "node_modules" / "generated.py",
    ]

    for path in ignored_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "class NoiseSymbol:\n"
            "    pass\n",
            encoding="utf-8",
        )

    index = RepositoryIndex.build(tmp_path)

    assert len(index.find_symbol("RealSymbol")) == 1
    assert index.find_symbol("NoiseSymbol") == ()

def test_repository_index_builds_internal_dependency(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "tools.py").write_text(
        "class ToolExecutor:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (package / "agent.py").write_text(
        "from example.tools import ToolExecutor\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    assert index.dependencies == (
        FileDependency(
            source=PurePosixPath("src/example/agent.py"),
            target=PurePosixPath("src/example/tools.py"),
        ),
    )

def test_repository_index_ignores_external_import(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "import json\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    assert index.dependencies == ()

def test_repository_index_deduplicates_file_dependencies(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "tools.py").write_text(
        "class First:\n"
        "    pass\n\n"
        "class Second:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (package / "agent.py").write_text(
        "from example.tools import First\n"
        "from example.tools import Second\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    assert index.dependencies == (
        FileDependency(
            source=PurePosixPath("src/example/agent.py"),
            target=PurePosixPath("src/example/tools.py"),
        ),
    )