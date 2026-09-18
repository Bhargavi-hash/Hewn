from __future__ import annotations

import ast
import difflib
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ground_edit import GroundingResult, ground_old_text

RESEARCH_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = RESEARCH_DIR / "fixtures"
TASKS_PATH = RESEARCH_DIR / "tasks.json"

SOURCE_RESULTS_PATH = (
    RESEARCH_DIR
    / "results"
    / "normalized-output-run-001.json"
)

RESULTS_PATH = (
    RESEARCH_DIR
    / "results"
    / "deterministic-grounding-replay-run-001.json"
)


@dataclass(frozen=True)
class Edit:
    path: str
    old: str
    new: str


@dataclass(frozen=True)
class GroundedEdit:
    path: str
    original_old: str
    grounded_old: str
    new: str
    grounding_strategy: str
    grounding_candidates: int


@dataclass(frozen=True)
class FailedGrounding:
    edit_index: int
    path: str
    original_old: str
    strategy: str | None
    candidates: int
    error: str


@dataclass(frozen=True)
class GroundingPreflight:
    valid: bool
    edits: tuple[GroundedEdit, ...]
    failure: FailedGrounding | None


@dataclass(frozen=True)
class VerificationResult:
    returncode: int
    passed: bool
    raw_output: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_tasks() -> dict[str, dict[str, Any]]:
    raw = load_json(TASKS_PATH)

    if isinstance(raw, dict) and "tasks" in raw:
        raw_tasks = raw["tasks"]
    else:
        raw_tasks = raw

    if isinstance(raw_tasks, list):
        return {
            str(task["id"]): task
            for task in raw_tasks
        }

    if isinstance(raw_tasks, dict):
        return {
            str(task_id): task
            for task_id, task in raw_tasks.items()
        }

    raise ValueError(
        "tasks.json must contain a task list or mapping"
    )


def load_source_records() -> list[dict[str, Any]]:
    data = load_json(SOURCE_RESULTS_PATH)

    records = data.get("records")

    if not isinstance(records, list):
        raise TypeError(
            "Source result file does not contain "
            "a records list"
        )

    return records


def parse_recorded_edits(
    record: dict[str, Any],
) -> tuple[Edit, ...]:
    raw_edits = record.get("proposed_edits")

    if not isinstance(raw_edits, list):
        raise TypeError(
            f"{record.get('task_id')}: "
            "missing proposed_edits"
        )

    edits: list[Edit] = []

    for raw_edit in raw_edits:
        if not isinstance(raw_edit, dict):
            raise TypeError(
                "Recorded edit must be an object"
            )

        path = raw_edit.get("path")
        old = raw_edit.get("old")
        new = raw_edit.get("new")
        
        if not isinstance(path, str):
            raise TypeError(
                "Recorded edit path must be a string"
            )
        
        if not isinstance(old, str):
            raise TypeError(
                "Recorded edit old text must be a string"
            )
        
        if not isinstance(new, str):
            raise TypeError(
                "Recorded edit new text must be a string"
            )
        
        edits.append(
            Edit(
                path=path,
                old=old,
                new=new,
            )
        )

    return tuple(edits)


def resolve_relative_file(
    root: Path,
    relative_path: str,
) -> Path:
    candidate = (root / relative_path).resolve()
    resolved_root = root.resolve()

    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            f"Path escapes fixture workspace: "
            f"{relative_path}"
        ) from exc

    return candidate


def grounding_error(
    result: GroundingResult,
) -> str:
    if result.candidates > 1:
        return (
            "Grounding was ambiguous: "
            f"{result.candidates} candidates"
        )

    return (
        "Text to replace was not found and "
        "could not be deterministically grounded"
    )


def preflight_with_grounding(
    *,
    root: Path,
    edits: tuple[Edit, ...],
) -> GroundingPreflight:
    simulated: dict[Path, str] = {}
    grounded: list[GroundedEdit] = []

    for index, edit in enumerate(edits):
        try:
            path = resolve_relative_file(
                root,
                edit.path,
            )
        except ValueError as exc:
            return GroundingPreflight(
                valid=False,
                edits=tuple(grounded),
                failure=FailedGrounding(
                    edit_index=index,
                    path=edit.path,
                    original_old=edit.old,
                    strategy=None,
                    candidates=0,
                    error=str(exc),
                ),
            )

        if not path.is_file():
            return GroundingPreflight(
                valid=False,
                edits=tuple(grounded),
                failure=FailedGrounding(
                    edit_index=index,
                    path=edit.path,
                    original_old=edit.old,
                    strategy=None,
                    candidates=0,
                    error="Target file does not exist",
                ),
            )

        if not edit.old:
            return GroundingPreflight(
                valid=False,
                edits=tuple(grounded),
                failure=FailedGrounding(
                    edit_index=index,
                    path=edit.path,
                    original_old=edit.old,
                    strategy=None,
                    candidates=0,
                    error=(
                        "Text to replace must not "
                        "be empty"
                    ),
                ),
            )

        if edit.old == edit.new:
            return GroundingPreflight(
                valid=False,
                edits=tuple(grounded),
                failure=FailedGrounding(
                    edit_index=index,
                    path=edit.path,
                    original_old=edit.old,
                    strategy=None,
                    candidates=0,
                    error=(
                        "Replacement must change "
                        "the source text"
                    ),
                ),
            )

        if path not in simulated:
            try:
                simulated[path] = path.read_text()
            except UnicodeDecodeError:
                return GroundingPreflight(
                    valid=False,
                    edits=tuple(grounded),
                    failure=FailedGrounding(
                        edit_index=index,
                        path=edit.path,
                        original_old=edit.old,
                        strategy=None,
                        candidates=0,
                        error=(
                            "Target file is not "
                            "valid UTF-8"
                        ),
                    ),
                )

        contents = simulated[path]

        result = ground_old_text(
            contents=contents,
            proposed_old=edit.old,
        )

        if (
            not result.matched
            or result.grounded_old is None
            or result.strategy is None
        ):
            return GroundingPreflight(
                valid=False,
                edits=tuple(grounded),
                failure=FailedGrounding(
                    edit_index=index,
                    path=edit.path,
                    original_old=edit.old,
                    strategy=result.strategy,
                    candidates=result.candidates,
                    error=grounding_error(result),
                ),
            )

        grounded_old = result.grounded_old

        occurrences = contents.count(
            grounded_old
        )

        if occurrences != 1:
            return GroundingPreflight(
                valid=False,
                edits=tuple(grounded),
                failure=FailedGrounding(
                    edit_index=index,
                    path=edit.path,
                    original_old=edit.old,
                    strategy=result.strategy,
                    candidates=occurrences,
                    error=(
                        "Grounded source is not "
                        "uniquely replaceable"
                    ),
                ),
            )

        simulated[path] = contents.replace(
            grounded_old,
            edit.new,
            1,
        )

        grounded.append(
            GroundedEdit(
                path=edit.path,
                original_old=edit.old,
                grounded_old=grounded_old,
                new=edit.new,
                grounding_strategy=result.strategy,
                grounding_candidates=(
                    result.candidates
                ),
            )
        )

    return GroundingPreflight(
        valid=True,
        edits=tuple(grounded),
        failure=None,
    )


def commit_grounded_edits(
    *,
    root: Path,
    edits: tuple[GroundedEdit, ...],
) -> None:
    simulated: dict[Path, str] = {}

    for edit in edits:
        path = resolve_relative_file(
            root,
            edit.path,
        )

        if path not in simulated:
            simulated[path] = path.read_text()

        contents = simulated[path]

        occurrences = contents.count(
            edit.grounded_old
        )

        if occurrences != 1:
            raise RuntimeError(
                "Committed grounding no longer "
                "matches preflight state"
            )

        simulated[path] = contents.replace(
            edit.grounded_old,
            edit.new,
            1,
        )

    for path, contents in simulated.items():
        path.write_text(contents)


def snapshot_python_files(
    root: Path,
) -> dict[str, str]:
    snapshot: dict[str, str] = {}

    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        snapshot[str(relative)] = path.read_text()

    return snapshot


def make_diff(
    before: dict[str, str],
    after: dict[str, str],
) -> str:
    chunks: list[str] = []

    paths = sorted(
        set(before) | set(after)
    )

    for path in paths:
        old = before.get(path, "")
        new = after.get(path, "")

        if old == new:
            continue

        chunks.extend(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )

    return "".join(chunks)


def count_changed_files(
    before: dict[str, str],
    after: dict[str, str],
) -> int:
    return sum(
        before.get(path) != after.get(path)
        for path in set(before) | set(after)
    )


def count_diff_lines(
    diff: str,
) -> tuple[int, int]:
    added = 0
    removed = 0

    for line in diff.splitlines():
        if line.startswith(("+++", "---")):
            continue

        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1

    return added, removed


def python_syntax_valid(
    root: Path,
) -> bool:
    for path in root.rglob("*.py"):
        try:
            ast.parse(path.read_text())
        except (
            SyntaxError,
            UnicodeDecodeError,
        ):
            return False

    return True


def run_pytest(
    root: Path,
) -> VerificationResult:
    completed = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "-q",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    output = (
        completed.stdout
        + completed.stderr
    )

    return VerificationResult(
        returncode=completed.returncode,
        passed=completed.returncode == 0,
        raw_output=output,
    )


def classify_outcome(
    *,
    preflight_valid: bool,
    syntax_valid: bool,
    verification_passed: bool,
    changed_files: int,
) -> str:
    if not preflight_valid:
        return "application_failure"

    if not syntax_valid:
        return "invalid_code"

    if not verification_passed:
        return "verification_failure"

    if changed_files == 0:
        return "verification_failure"

    return "success"


def copy_fixture(
    task_id: str,
    destination: Path,
) -> Path:
    source = FIXTURES_DIR / task_id

    if not source.is_dir():
        raise FileNotFoundError(
            f"Fixture not found: {source}"
        )

    workspace = destination / task_id

    shutil.copytree(
        source,
        workspace,
    )

    return workspace


def replay_record(
    *,
    record: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(record["task_id"])

    with tempfile.TemporaryDirectory(
        prefix=f"hewn-{task_id}-"
    ) as temp_dir:
        root = copy_fixture(
            task_id,
            Path(temp_dir),
        )

        verification_before = run_pytest(
            root
        )

        before = snapshot_python_files(
            root
        )

        edits = parse_recorded_edits(
            record
        )

        preflight = preflight_with_grounding(
            root=root,
            edits=edits,
        )

        committed = False

        if preflight.valid:
            commit_grounded_edits(
                root=root,
                edits=preflight.edits,
            )
            committed = True

        after = snapshot_python_files(
            root
        )

        diff = make_diff(
            before,
            after,
        )

        changed_files = count_changed_files(
            before,
            after,
        )

        added, removed = count_diff_lines(
            diff
        )

        syntax_valid = python_syntax_valid(
            root
        )

        verification_after = run_pytest(
            root
        )

        outcome = classify_outcome(
            preflight_valid=preflight.valid,
            syntax_valid=syntax_valid,
            verification_passed=(
                verification_after.passed
            ),
            changed_files=changed_files,
        )

        grounding_used = any(
            edit.grounding_strategy
            != "exact"
            for edit in preflight.edits
        )

        return {
            "task_id": task_id,
            "category": task.get(
                "category"
            ),
            "task": task.get("task"),
            "source_condition": (
                "normalized_output"
            ),
            "source_result_outcome": (
                record.get("outcome")
            ),
            "model_reused": True,
            "new_model_calls": 0,
            "proposed_edits": [
                asdict(edit)
                for edit in edits
            ],
            "preflight_valid": (
                preflight.valid
            ),
            "grounded_edits": [
                asdict(edit)
                for edit in preflight.edits
            ],
            "grounding_used": grounding_used,
            "grounding_failure": (
                asdict(preflight.failure)
                if preflight.failure
                else None
            ),
            "committed": committed,
            "syntax_valid": syntax_valid,
            "behavior_success": (
                verification_after.passed
            ),
            "outcome": outcome,
            "changed_files": changed_files,
            "diff_added_lines": added,
            "diff_removed_lines": removed,
            "diff": diff,
            "verification_before": (
                asdict(verification_before)
            ),
            "verification_after": (
                asdict(verification_after)
            ),
        }


def build_summary(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    outcomes: dict[str, int] = {}

    for record in records:
        outcome = str(record["outcome"])
        outcomes[outcome] = (
            outcomes.get(outcome, 0) + 1
        )

    grounding_used = sum(
        bool(record["grounding_used"])
        for record in records
    )

    return {
        "tasks": len(records),
        "behavior_success": sum(
            bool(record["behavior_success"])
            for record in records
        ),
        "preflight_success": sum(
            bool(record["preflight_valid"])
            for record in records
        ),
        "committed_batches": sum(
            bool(record["committed"])
            for record in records
        ),
        "grounding_used": grounding_used,
        "new_model_calls": 0,
        "outcomes": outcomes,
    }


def main() -> None:
    if RESULTS_PATH.exists():
        raise FileExistsError(
            f"Refusing to overwrite: "
            f"{RESULTS_PATH}"
        )

    tasks = load_tasks()
    source_records = load_source_records()

    print(
        "Experiment: deterministic grounding "
        "offline replay"
    )
    print(
        "Source proposals: "
        "normalized-output-run-001.json"
    )
    print("New model calls: 0")
    print(
        "Changed variable: deterministic "
        "old-text grounding"
    )
    print(f"Tasks: {len(source_records)}")
    print()

    records: list[dict[str, Any]] = []

    for source_record in source_records:
        task_id = str(
            source_record["task_id"]
        )

        if task_id not in tasks:
            raise KeyError(
                f"Unknown task: {task_id}"
            )

        result = replay_record(
            record=source_record,
            task=tasks[task_id],
        )

        records.append(result)

        grounding = (
            "GROUND"
            if result["grounding_used"]
            else "EXACT"
        )

        if not result["preflight_valid"]:
            grounding = "REJECT"

        print(
            f"{task_id}: "
            f"source={result['source_result_outcome']} "
            f"replay={result['outcome']} "
            f"behavior="
            f"{'PASS' if result['behavior_success'] else 'FAIL'} "
            f"preflight="
            f"{'PASS' if result['preflight_valid'] else 'FAIL'} "
            f"application={grounding}"
        )

        failure = result[
            "grounding_failure"
        ]

        if failure is not None:
            print(
                "  grounding_error="
                f"{failure['error']}"
            )

    summary = build_summary(records)

    output = {
        "metadata": {
            "module": 7,
            "experiment": (
                "deterministic_grounding_"
                "offline_replay"
            ),
            "source_results": str(
                SOURCE_RESULTS_PATH
            ),
            "source_condition": (
                "normalized_output"
            ),
            "model_proposals_reused": True,
            "new_model_calls": 0,
            "editing_representation": (
                "atomic edit_batch"
            ),
            "underlying_primitive": (
                "exact replacement with "
                "conservative deterministic "
                "grounding fallback"
            ),
            "grounding_strategies": [
                "exact",
                "token_equivalent",
            ],
            "verification_oracle": "pytest",
            "runs_per_task": 1,
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
        "Behavior success: "
        f"{summary['behavior_success']}/"
        f"{summary['tasks']}"
    )
    print(
        "Preflight success: "
        f"{summary['preflight_success']}/"
        f"{summary['tasks']}"
    )
    print(
        "Committed batches: "
        f"{summary['committed_batches']}/"
        f"{summary['tasks']}"
    )
    print(
        "Grounding used: "
        f"{summary['grounding_used']}/"
        f"{summary['tasks']}"
    )
    print(
        f"Outcomes: {summary['outcomes']}"
    )
    print("New model calls: 0")
    print()
    print(f"Results: {RESULTS_PATH}")


if __name__ == "__main__":
    main()