from __future__ import annotations

import ast
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
TEST_ROOT = ROOT / "tests"

RESULTS_PATH = (
    ROOT
    / "research"
    / "007-execution-feedback"
    / "results"
    / "targeted-verification-selection-run-001.json"
)


CASES = (
    (
        "TV-001",
        "src/hewn/completion.py",
    ),
    (
        "TV-002",
        "src/hewn/workspace.py",
    ),
    (
        "TV-003",
        "src/hewn/tools.py",
    ),
    (
        "TV-004",
        "src/hewn/repository/python_parser.py",
    ),
    (
        "TV-005",
        "src/hewn/repository/index.py",
    ),
    (
        "TV-006",
        "src/hewn/retrieval/models.py",
    ),
    (
        "TV-007",
        "src/hewn/retrieval/router.py",
    ),
    (
        "TV-008",
        "src/hewn/agent.py",
    ),
)


@dataclass(frozen=True)
class PythonModule:
    module: str
    path: str
    is_test: bool
    imports: tuple[str, ...]


@dataclass(frozen=True)
class PytestResult:
    returncode: int
    passed: bool
    elapsed_seconds: float
    output: str


def module_name_for_path(
    path: Path,
) -> str:
    relative: Path

    try:
        relative = path.relative_to(SRC_ROOT)
    except ValueError:
        relative = path.relative_to(ROOT)

    parts = list(relative.with_suffix("").parts)

    if parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


def imports_from_file(
    path: Path,
) -> tuple[str, ...]:
    tree = ast.parse(path.read_text())

    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    alias.name == "hewn"
                    or alias.name.startswith("hewn.")
                ):
                    imports.add(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module

            if (
                module is not None
                and (
                    module == "hewn"
                    or module.startswith("hewn.")
                )
            ):
                imports.add(module)

    return tuple(sorted(imports))


def discover_modules() -> dict[str, PythonModule]:
    modules: dict[str, PythonModule] = {}

    production_files = sorted(
        (SRC_ROOT / "hewn").rglob("*.py")
    )
    test_files = sorted(
        TEST_ROOT.rglob("test_*.py")
    )

    for path in production_files:
        module = module_name_for_path(path)

        modules[module] = PythonModule(
            module=module,
            path=str(path.relative_to(ROOT)),
            is_test=False,
            imports=imports_from_file(path),
        )

    for path in test_files:
        module = module_name_for_path(path)

        modules[module] = PythonModule(
            module=module,
            path=str(path.relative_to(ROOT)),
            is_test=True,
            imports=imports_from_file(path),
        )

    return modules


def resolve_import_targets(
    imported: str,
    known_modules: set[str],
) -> set[str]:
    targets: set[str] = set()

    current = imported

    while current:
        if current in known_modules:
            targets.add(current)

        if "." not in current:
            break

        current = current.rsplit(".", 1)[0]

    return targets


def build_reverse_graph(
    modules: dict[str, PythonModule],
) -> dict[str, set[str]]:
    known = set(modules)
    reverse: dict[str, set[str]] = {
        module: set()
        for module in modules
    }

    for importer, info in modules.items():
        for imported in info.imports:
            for target in resolve_import_targets(
                imported,
                known,
            ):
                reverse[target].add(importer)

    return reverse


def transitive_dependents(
    *,
    changed_module: str,
    reverse_graph: dict[str, set[str]],
) -> set[str]:
    visited: set[str] = set()
    pending = [changed_module]

    while pending:
        current = pending.pop()

        for dependent in reverse_graph.get(
            current,
            set(),
        ):
            if dependent in visited:
                continue

            visited.add(dependent)
            pending.append(dependent)

    return visited


def selected_tests(
    *,
    changed_module: str,
    modules: dict[str, PythonModule],
    reverse_graph: dict[str, set[str]],
) -> list[str]:
    dependents = transitive_dependents(
        changed_module=changed_module,
        reverse_graph=reverse_graph,
    )

    return sorted(
        modules[module].path
        for module in dependents
        if modules[module].is_test
    )


def direct_tests(
    *,
    changed_module: str,
    modules: dict[str, PythonModule],
) -> list[str]:
    known = set(modules)

    selected: list[str] = []

    for info in modules.values():
        if not info.is_test:
            continue

        imported_targets: set[str] = set()

        for imported in info.imports:
            imported_targets.update(
                resolve_import_targets(
                    imported,
                    known,
                )
            )

        if changed_module in imported_targets:
            selected.append(info.path)

    return sorted(selected)


def changed_module_from_path(
    relative_path: str,
) -> str:
    path = ROOT / relative_path
    return module_name_for_path(path)


def run_pytest(
    test_paths: list[str],
) -> PytestResult:
    command = [
        "python",
        "-m",
        "pytest",
        "-q",
        *test_paths,
    ]

    started = time.monotonic()

    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    elapsed = time.monotonic() - started

    return PytestResult(
        returncode=completed.returncode,
        passed=completed.returncode == 0,
        elapsed_seconds=elapsed,
        output=completed.stdout + completed.stderr,
    )


def main() -> None:
    if RESULTS_PATH.exists():
        raise FileExistsError(
            f"Refusing to overwrite: {RESULTS_PATH}"
        )

    modules = discover_modules()
    reverse_graph = build_reverse_graph(modules)

    production_module_count = sum(
        1
        for module_info in modules.values()
        if not module_info.is_test
    )

    all_tests = sorted(
        module_info.path
        for module_info in modules.values()
        if module_info.is_test
    )

    print(
        "Experiment: deterministic targeted "
        "verification selection"
    )
    print(
        "Selector: transitive reverse import graph"
    )
    print(
        "Baseline: direct test imports"
    )
    print(
        f"Production modules: "
        f"{production_module_count}"
    )
    print(
        f"Test files: {len(all_tests)}"
    )
    print(
        f"Cases: {len(CASES)}"
    )
    print()

    records: list[dict[str, Any]] = []

    for case_id, changed_path in CASES:
        changed_module = changed_module_from_path(
            changed_path
        )

        if changed_module not in modules:
            raise KeyError(
                f"Unknown changed module: "
                f"{changed_module}"
            )

        direct = direct_tests(
            changed_module=changed_module,
            modules=modules,
        )

        transitive = selected_tests(
            changed_module=changed_module,
            modules=modules,
            reverse_graph=reverse_graph,
        )

        transitive_only = sorted(
            set(transitive) - set(direct)
        )

        reduction = (
            1.0 - len(transitive) / len(all_tests)
            if all_tests
            else 0.0
        )

        record = {
            "case_id": case_id,
            "changed_path": changed_path,
            "changed_module": changed_module,
            "direct_tests": direct,
            "direct_test_count": len(direct),
            "selected_tests": transitive,
            "selected_test_count": len(transitive),
            "transitive_only_tests": transitive_only,
            "transitive_only_count": len(
                transitive_only
            ),
            "full_test_file_count": len(
                all_tests
            ),
            "test_file_reduction_fraction": (
                reduction
            ),
        }

        records.append(record)

        print(
            f"{case_id}: "
            f"{changed_module}"
        )
        print(
            f"  direct={len(direct)} "
            f"transitive={len(transitive)} "
            f"full={len(all_tests)} "
            f"reduction={reduction:.1%}"
        )

        if transitive_only:
            print(
                "  transitive-only="
                + ", ".join(transitive_only)
            )

        union_selected_set: set[str] = set()

        for record in records:
            selected = record["selected_tests"]

            if not isinstance(selected, list):
                raise TypeError(
                    "selected_tests must be a list"
                )

            for test_path in selected:
                if not isinstance(test_path, str):
                    raise TypeError(
                        "Selected test path must be a string"
                    )

                union_selected_set.add(test_path)

    union_selected = sorted(
        union_selected_set
    )

    targeted_clean_result = run_pytest(
        union_selected
    )
    full_clean_result = run_pytest(
        all_tests
    )

    output = {
        "metadata": {
            "module": 7,
            "experiment": (
                "targeted_verification_selection"
            ),
            "selector": (
                "transitive reverse import graph"
            ),
            "baseline": "direct test imports",
            "model_calls": 0,
            "mutations": 0,
            "production_modules": (
                production_module_count
            ),
            "test_files": len(all_tests),
        },
        "cases": records,
        "clean_verification": {
            "union_selected_tests": (
                union_selected
            ),
            "union_selected_count": len(
                union_selected
            ),
            "targeted": asdict(
                targeted_clean_result
            ),
            "full": asdict(
                full_clean_result
            ),
        },
    }

    RESULTS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULTS_PATH.write_text(
        json.dumps(
            output,
            indent=2,
        )
        + "\n"
    )

    print()
    print("Clean verification")
    print(
        "Targeted union: "
        f"{len(union_selected)}/"
        f"{len(all_tests)} test files, "
        f"{targeted_clean_result.elapsed_seconds:.2f}s, "
        f"{'PASS' if targeted_clean_result.passed else 'FAIL'}"
    )
    print(
        "Full suite: "
        f"{len(all_tests)}/"
        f"{len(all_tests)} test files, "
        f"{full_clean_result.elapsed_seconds:.2f}s, "
        f"{'PASS' if full_clean_result.passed else 'FAIL'}"
    )
    print()
    print(
        f"Results: {RESULTS_PATH}"
    )


if __name__ == "__main__":
    main()