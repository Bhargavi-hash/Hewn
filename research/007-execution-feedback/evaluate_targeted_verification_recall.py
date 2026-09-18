from __future__ import annotations

import ast
import json
import shutil
import subprocess
import tempfile
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
    / "targeted-verification-recall-run-001.json"
)


@dataclass(frozen=True)
class Mutation:
    mutation_id: str
    path: str
    old: str
    new: str


@dataclass(frozen=True)
class PythonModule:
    module: str
    path: str
    is_test: bool
    imports: tuple[str, ...]


@dataclass(frozen=True)
class PytestResult:
    returncode: int
    detected_failure: bool
    elapsed_seconds: float
    output: str


MUTATIONS = (
    Mutation(
        mutation_id="M-001",
        path="src/hewn/completion.py",
        old=(
            "return self.verification_state "
            "is VerificationState.PASSED"
        ),
        new=(
            "return self.verification_state "
            "is VerificationState.FAILED"
        ),
    ),
    Mutation(
        mutation_id="M-002",
        path="src/hewn/workspace.py",
        old=(
            "if not candidate.is_relative_to("
            "self.root):"
        ),
        new=(
            "if candidate.is_relative_to("
            "self.root):"
        ),
    ),
    Mutation(
        mutation_id="M-003",
        path="src/hewn/tools.py",
        old="return self._tools.get(name)",
        new="return None",
    ),
    Mutation(
        mutation_id="M-004",
        path=(
            "src/hewn/repository/"
            "python_parser.py"
        ),
        old="return name",
        new='return f"{parent}.{name}"',
    ),
    Mutation(
        mutation_id="M-005",
        path="src/hewn/repository/index.py",
        old=(
            "return not any(\n"
            "        part in _IGNORED_DIRECTORY_NAMES\n"
            "        for part in relative.parts\n"
            "    )"
        ),
        new=(
            "return any(\n"
            "        part in _IGNORED_DIRECTORY_NAMES\n"
            "        for part in relative.parts\n"
            "    )"
        ),
    ),
    Mutation(
        mutation_id="M-006",
        path="src/hewn/retrieval/models.py",
        old="if not self.text.strip():",
        new="if self.text.strip():",
    ),
    Mutation(
        mutation_id="M-007",
        path="src/hewn/retrieval/router.py",
        old="if len(matches) != 1:",
        new="if len(matches) == 1:",
    ),
    Mutation(
        mutation_id="M-008",
        path="src/hewn/agent.py",
        old="return output or \"\"",
        new="return \"\"",
    ),
)


def module_name_for_path(
    *,
    path: Path,
    root: Path,
) -> str:
    src_root = root / "src"

    try:
        relative = path.relative_to(src_root)
    except ValueError:
        relative = path.relative_to(root)

    parts = list(
        relative.with_suffix("").parts
    )

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


def discover_modules(
    root: Path,
) -> dict[str, PythonModule]:
    modules: dict[str, PythonModule] = {}

    production_files = sorted(
        (root / "src" / "hewn").rglob(
            "*.py"
        )
    )
    test_files = sorted(
        (root / "tests").rglob(
            "test_*.py"
        )
    )

    for path in production_files:
        module = module_name_for_path(
            path=path,
            root=root,
        )

        modules[module] = PythonModule(
            module=module,
            path=str(path.relative_to(root)),
            is_test=False,
            imports=imports_from_file(path),
        )

    for path in test_files:
        module = module_name_for_path(
            path=path,
            root=root,
        )

        modules[module] = PythonModule(
            module=module,
            path=str(path.relative_to(root)),
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
            targets = resolve_import_targets(
                imported,
                known,
            )

            for target in targets:
                reverse[target].add(importer)

    return reverse


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

        targets: set[str] = set()

        for imported in info.imports:
            targets.update(
                resolve_import_targets(
                    imported,
                    known,
                )
            )

        if changed_module in targets:
            selected.append(info.path)

    return sorted(selected)


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


def transitive_tests(
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


def apply_mutation(
    *,
    root: Path,
    mutation: Mutation,
) -> None:
    path = root / mutation.path

    if not path.is_file():
        raise FileNotFoundError(
            f"Mutation target missing: {path}"
        )

    contents = path.read_text()
    count = contents.count(mutation.old)

    if count != 1:
        raise ValueError(
            f"{mutation.mutation_id}: "
            f"expected old text exactly once, "
            f"found {count}"
        )

    if mutation.old == mutation.new:
        raise ValueError(
            f"{mutation.mutation_id}: "
            "mutation is a no-op"
        )

    path.write_text(
        contents.replace(
            mutation.old,
            mutation.new,
            1,
        )
    )


def run_pytest(
    *,
    root: Path,
    test_paths: list[str],
) -> PytestResult:
    if not test_paths:
        raise ValueError(
            "Verification policy selected no tests"
        )

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
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    elapsed = time.monotonic() - started

    return PytestResult(
        returncode=completed.returncode,
        detected_failure=(
            completed.returncode != 0
        ),
        elapsed_seconds=elapsed,
        output=(
            completed.stdout
            + completed.stderr
        ),
    )


def copy_repository(
    destination: Path,
) -> Path:
    workspace = destination / "Hewn"

    shutil.copytree(
        ROOT,
        workspace,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            "results",
        ),
    )

    return workspace


def evaluate_mutation(
    mutation: Mutation,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=(
            f"hewn-targeted-"
            f"{mutation.mutation_id}-"
        )
    ) as temp_dir:
        workspace = copy_repository(
            Path(temp_dir)
        )

        modules = discover_modules(workspace)
        reverse_graph = build_reverse_graph(
            modules
        )

        changed_module = module_name_for_path(
            path=workspace / mutation.path,
            root=workspace,
        )

        direct = direct_tests(
            changed_module=changed_module,
            modules=modules,
        )

        transitive = transitive_tests(
            changed_module=changed_module,
            modules=modules,
            reverse_graph=reverse_graph,
        )

        full = sorted(
            info.path
            for info in modules.values()
            if info.is_test
        )

        if not direct:
            raise ValueError(
                f"{mutation.mutation_id}: "
                "direct policy selected no tests"
            )

        if not transitive:
            raise ValueError(
                f"{mutation.mutation_id}: "
                "transitive policy selected no tests"
            )

        apply_mutation(
            root=workspace,
            mutation=mutation,
        )

        syntax_valid = True

        try:
            ast.parse(
                (
                    workspace
                    / mutation.path
                ).read_text()
            )
        except SyntaxError:
            syntax_valid = False

        if not syntax_valid:
            raise ValueError(
                f"{mutation.mutation_id}: "
                "mutation produced invalid syntax"
            )

        direct_result = run_pytest(
            root=workspace,
            test_paths=direct,
        )

        transitive_result = run_pytest(
            root=workspace,
            test_paths=transitive,
        )

        full_result = run_pytest(
            root=workspace,
            test_paths=full,
        )

        full_detected = (
            full_result.detected_failure
        )

        direct_recall = (
            direct_result.detected_failure
            if full_detected
            else None
        )

        transitive_recall = (
            transitive_result.detected_failure
            if full_detected
            else None
        )

        return {
            "mutation": asdict(mutation),
            "changed_module": changed_module,
            "syntax_valid": syntax_valid,
            "direct_tests": direct,
            "direct_test_count": len(direct),
            "transitive_tests": transitive,
            "transitive_test_count": len(
                transitive
            ),
            "full_test_count": len(full),
            "direct_reduction_fraction": (
                1.0 - len(direct) / len(full)
            ),
            "transitive_reduction_fraction": (
                1.0
                - len(transitive) / len(full)
            ),
            "direct_result": asdict(
                direct_result
            ),
            "transitive_result": asdict(
                transitive_result
            ),
            "full_result": asdict(
                full_result
            ),
            "full_detected_failure": (
                full_detected
            ),
            "direct_detected_when_full_did": (
                direct_recall
            ),
            "transitive_detected_when_full_did": (
                transitive_recall
            ),
        }


def build_summary(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    detectable = [
        record
        for record in records
        if record["full_detected_failure"]
    ]

    direct_detected = sum(
        record[
            "direct_detected_when_full_did"
        ]
        is True
        for record in detectable
    )

    transitive_detected = sum(
        record[
            "transitive_detected_when_full_did"
        ]
        is True
        for record in detectable
    )

    direct_total_time = sum(
        float(
            record["direct_result"][
                "elapsed_seconds"
            ]
        )
        for record in records
    )

    transitive_total_time = sum(
        float(
            record["transitive_result"][
                "elapsed_seconds"
            ]
        )
        for record in records
    )

    full_total_time = sum(
        float(
            record["full_result"][
                "elapsed_seconds"
            ]
        )
        for record in records
    )

    average_direct_files = (
        sum(
            int(record["direct_test_count"])
            for record in records
        )
        / len(records)
    )

    average_transitive_files = (
        sum(
            int(
                record[
                    "transitive_test_count"
                ]
            )
            for record in records
        )
        / len(records)
    )

    average_full_files = (
        sum(
            int(record["full_test_count"])
            for record in records
        )
        / len(records)
    )

    return {
        "mutations": len(records),
        "full_suite_detectable_mutations": len(
            detectable
        ),
        "direct_detected": direct_detected,
        "transitive_detected": (
            transitive_detected
        ),
        "direct_failure_recall": (
            direct_detected / len(detectable)
            if detectable
            else None
        ),
        "transitive_failure_recall": (
            transitive_detected
            / len(detectable)
            if detectable
            else None
        ),
        "average_direct_test_files": (
            average_direct_files
        ),
        "average_transitive_test_files": (
            average_transitive_files
        ),
        "average_full_test_files": (
            average_full_files
        ),
        "direct_total_seconds": (
            direct_total_time
        ),
        "transitive_total_seconds": (
            transitive_total_time
        ),
        "full_total_seconds": (
            full_total_time
        ),
    }


def main() -> None:
    if RESULTS_PATH.exists():
        raise FileExistsError(
            f"Refusing to overwrite: "
            f"{RESULTS_PATH}"
        )

    print(
        "Experiment: targeted verification "
        "failure recall"
    )
    print(
        "Policies: direct imports vs "
        "transitive reverse imports vs full suite"
    )
    print(
        "Mutation set: frozen semantic "
        "single-site mutations"
    )
    print(
        "Model calls: 0"
    )
    print(
        f"Mutations: {len(MUTATIONS)}"
    )
    print()

    records: list[dict[str, Any]] = []

    for mutation in MUTATIONS:
        record = evaluate_mutation(
            mutation
        )
        records.append(record)

        direct = record["direct_result"]
        transitive = record[
            "transitive_result"
        ]
        full = record["full_result"]

        print(
            f"{mutation.mutation_id}: "
            f"{record['changed_module']}"
        )
        print(
            "  tests: "
            f"direct={record['direct_test_count']} "
            f"transitive="
            f"{record['transitive_test_count']} "
            f"full={record['full_test_count']}"
        )
        print(
            "  detected: "
            f"direct="
            f"{direct['detected_failure']} "
            f"transitive="
            f"{transitive['detected_failure']} "
            f"full="
            f"{full['detected_failure']}"
        )
        print(
            "  time: "
            f"direct="
            f"{direct['elapsed_seconds']:.2f}s "
            f"transitive="
            f"{transitive['elapsed_seconds']:.2f}s "
            f"full="
            f"{full['elapsed_seconds']:.2f}s"
        )

    summary = build_summary(records)

    output = {
        "metadata": {
            "module": 7,
            "experiment": (
                "targeted_verification_"
                "failure_recall"
            ),
            "model_calls": 0,
            "mutation_count": len(
                MUTATIONS
            ),
            "mutation_policy": (
                "frozen semantic single-site"
            ),
            "verification_policies": [
                "direct_import_tests",
                "transitive_reverse_import_tests",
                "full_suite",
            ],
            "runs_per_mutation": 1,
        },
        "summary": summary,
        "records": records,
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
    print("Summary")
    print(
        "Full-suite-detectable mutations: "
        f"{summary['full_suite_detectable_mutations']}/"
        f"{summary['mutations']}"
    )
    print(
        "Direct failure recall: "
        f"{summary['direct_detected']}/"
        f"{summary['full_suite_detectable_mutations']}"
    )
    print(
        "Transitive failure recall: "
        f"{summary['transitive_detected']}/"
        f"{summary['full_suite_detectable_mutations']}"
    )
    print(
        "Average test files: "
        f"direct="
        f"{summary['average_direct_test_files']:.1f}, "
        f"transitive="
        f"{summary['average_transitive_test_files']:.1f}, "
        f"full="
        f"{summary['average_full_test_files']:.1f}"
    )
    print(
        "Total wall time: "
        f"direct="
        f"{summary['direct_total_seconds']:.2f}s, "
        f"transitive="
        f"{summary['transitive_total_seconds']:.2f}s, "
        f"full="
        f"{summary['full_total_seconds']:.2f}s"
    )
    print()
    print(
        f"Results: {RESULTS_PATH}"
    )


if __name__ == "__main__":
    main()