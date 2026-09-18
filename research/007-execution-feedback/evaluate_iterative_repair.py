from __future__ import annotations

import ast
import difflib
import json
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from normalize_pytest import normalize_pytest_output

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
    / "iterative-repair-run-001.json"
)

MODEL_NAME = "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"
MODEL_URL = "http://127.0.0.1:8080/v1/chat/completions"
TEMPERATURE = 0.0
MAX_TOKENS = 512
CONTEXT_WINDOW = 4096
TIMEOUT_SECONDS = 120
MAX_BATCH_EDITS = 6


@dataclass(frozen=True)
class Edit:
    path: str
    old: str
    new: str


@dataclass(frozen=True)
class PreflightResult:
    valid: bool
    error: str | None
    failed_edit_index: int | None


@dataclass(frozen=True)
class VerificationResult:
    returncode: int
    passed: bool
    raw_output: str


@dataclass(frozen=True)
class ModelCallResult:
    raw_response: str
    elapsed_seconds: float


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

    raise TypeError(
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


def parse_edit_objects(
    raw_edits: Any,
) -> tuple[Edit, ...]:
    if not isinstance(raw_edits, list):
        raise TypeError(
            "edits must be a list"
        )

    if not 1 <= len(raw_edits) <= MAX_BATCH_EDITS:
        raise ValueError(
            "edit_batch must contain between "
            f"1 and {MAX_BATCH_EDITS} edits"
        )

    edits: list[Edit] = []

    for raw_edit in raw_edits:
        if not isinstance(raw_edit, dict):
            raise TypeError(
                "Each edit must be an object"
            )

        if set(raw_edit) != {
            "path",
            "old",
            "new",
        }:
            raise ValueError(
                "Each edit must contain exactly "
                "path, old, and new"
            )

        path = raw_edit.get("path")
        old = raw_edit.get("old")
        new = raw_edit.get("new")

        if not isinstance(path, str):
            raise TypeError(
                "Edit path must be a string"
            )

        if not isinstance(old, str):
            raise TypeError(
                "Edit old text must be a string"
            )

        if not isinstance(new, str):
            raise TypeError(
                "Edit new text must be a string"
            )

        edits.append(
            Edit(
                path=path,
                old=old,
                new=new,
            )
        )

    return tuple(edits)


def parse_recorded_edits(
    record: dict[str, Any],
) -> tuple[Edit, ...]:
    return parse_edit_objects(
        record.get("proposed_edits")
    )


def parse_model_response(
    raw_response: str,
) -> tuple[Edit, ...]:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Model response is not strict JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise TypeError(
            "Model response must be an object"
        )

    if set(payload) != {"type", "edits"}:
        raise ValueError(
            "Model response must contain exactly "
            "type and edits"
        )

    if payload.get("type") != "edit_batch":
        raise ValueError(
            "Model response type must be edit_batch"
        )

    return parse_edit_objects(
        payload.get("edits")
    )


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
            "Path escapes fixture workspace: "
            f"{relative_path}"
        ) from exc

    return candidate


def preflight_exact(
    *,
    root: Path,
    edits: tuple[Edit, ...],
) -> PreflightResult:
    simulated: dict[Path, str] = {}

    for index, edit in enumerate(edits):
        try:
            path = resolve_relative_file(
                root,
                edit.path,
            )
        except ValueError as exc:
            return PreflightResult(
                valid=False,
                error=str(exc),
                failed_edit_index=index,
            )

        if not path.is_file():
            return PreflightResult(
                valid=False,
                error="Target file does not exist",
                failed_edit_index=index,
            )

        if not edit.old:
            return PreflightResult(
                valid=False,
                error=(
                    "Text to replace must not be empty"
                ),
                failed_edit_index=index,
            )

        if edit.old == edit.new:
            return PreflightResult(
                valid=False,
                error=(
                    "Replacement must change "
                    "the source text"
                ),
                failed_edit_index=index,
            )

        if path not in simulated:
            try:
                simulated[path] = path.read_text()
            except UnicodeDecodeError:
                return PreflightResult(
                    valid=False,
                    error=(
                        "Target file is not valid UTF-8"
                    ),
                    failed_edit_index=index,
                )

        contents = simulated[path]
        occurrences = contents.count(edit.old)

        if occurrences == 0:
            return PreflightResult(
                valid=False,
                error="Text to replace was not found",
                failed_edit_index=index,
            )

        if occurrences > 1:
            return PreflightResult(
                valid=False,
                error=(
                    "Text to replace occurs more "
                    "than once"
                ),
                failed_edit_index=index,
            )

        simulated[path] = contents.replace(
            edit.old,
            edit.new,
            1,
        )

    return PreflightResult(
        valid=True,
        error=None,
        failed_edit_index=None,
    )


def commit_edits(
    *,
    root: Path,
    edits: tuple[Edit, ...],
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

        if contents.count(edit.old) != 1:
            raise RuntimeError(
                "Workspace changed after preflight"
            )

        simulated[path] = contents.replace(
            edit.old,
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
        relative = str(path.relative_to(root))
        snapshot[relative] = path.read_text()

    return snapshot


def make_diff(
    before: dict[str, str],
    after: dict[str, str],
) -> str:
    chunks: list[str] = []

    for path in sorted(set(before) | set(after)):
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

    return VerificationResult(
        returncode=completed.returncode,
        passed=completed.returncode == 0,
        raw_output=(
            completed.stdout
            + completed.stderr
        ),
    )


def source_context(
    *,
    root: Path,
    source_files: list[str],
) -> str:
    chunks: list[str] = []

    for relative_path in source_files:
        path = resolve_relative_file(
            root,
            relative_path,
        )

        chunks.append(
            f"FILE: {relative_path}\n"
            f"{path.read_text()}"
        )

    return "\n\n".join(chunks)


def repair_system_prompt() -> str:
    return (
        "You repair Python repository code after a "
        "failed verification run.\n"
        "\n"
        "Return exactly one JSON object and nothing "
        "else.\n"
        "\n"
        "Required schema:\n"
        "{\n"
        '  "type": "edit_batch",\n'
        '  "edits": [\n'
        "    {\n"
        '      "path": "relative/path.py",\n'
        '      "old": "exact existing text",\n'
        '      "new": "replacement text"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "\n"
        f"Use between 1 and {MAX_BATCH_EDITS} edits.\n"
        "Every old value must occur exactly once in "
        "the CURRENT source shown to you.\n"
        "Preserve required indentation in replacement "
        "text.\n"
        "For insertion, replace a unique existing "
        "anchor with the anchor plus the inserted "
        "text.\n"
        "You may edit multiple locations or files when "
        "necessary.\n"
        "Do not return markdown.\n"
        "Do not explain the repair.\n"
        "Do not return a final answer.\n"
        "Do not edit tests.\n"
    )


def repair_user_prompt(
    *,
    task_text: str,
    feedback: dict[str, Any],
    source: str,
) -> str:
    return (
        "Task:\n"
        f"{task_text}\n"
        "\n"
        "The current implementation was modified once "
        "and still fails verification.\n"
        "\n"
        "Normalized execution evidence:\n"
        f"{json.dumps(feedback, indent=2)}\n"
        "\n"
        "CURRENT SOURCE:\n"
        f"{source}\n"
    )


def call_model(
    *,
    system_prompt: str,
    user_prompt: str,
) -> ModelCallResult:
    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    request = urllib.request.Request(
        MODEL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started = time.monotonic()

    try:
        with urllib.request.urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:
            response_data = json.loads(
                response.read().decode("utf-8")
            )
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not call local llama.cpp server"
        ) from exc

    elapsed = time.monotonic() - started

    try:
        content = response_data[
            "choices"
        ][0]["message"]["content"]
    except (
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise RuntimeError(
            "Unexpected llama.cpp response shape"
        ) from exc

    if not isinstance(content, str):
        raise TypeError(
            "Model response content is not a string"
        )

    return ModelCallResult(
        raw_response=content,
        elapsed_seconds=elapsed,
    )


def classify_final_outcome(
    *,
    initial_preflight: PreflightResult,
    initial_verification: VerificationResult | None,
    repair_eligible: bool,
    repair_protocol_success: bool | None,
    repair_preflight: PreflightResult | None,
    syntax_valid: bool,
    final_verification: VerificationResult,
) -> str:
    if not initial_preflight.valid:
        return "initial_application_failure"

    if (
        initial_verification is not None
        and initial_verification.passed
    ):
        return "initial_success"

    if not repair_eligible:
        return "verification_failure"

    if repair_protocol_success is False:
        return "repair_protocol_failure"

    if (
        repair_preflight is not None
        and not repair_preflight.valid
    ):
        return "repair_application_failure"

    if not syntax_valid:
        return "invalid_code"

    if final_verification.passed:
        return "recovered_success"

    return "verification_failure"


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


def source_files_for_task(
    task: dict[str, Any],
) -> list[str]:
    raw = task.get("source_files")

    if not isinstance(raw, list):
        raise TypeError(
            "Task source_files must be a list"
        )

    source_files: list[str] = []

    for item in raw:
        if not isinstance(item, str):
            raise TypeError(
                "Task source file must be a string"
            )

        source_files.append(item)

    return source_files


def task_text_for_task(
    task: dict[str, Any],
) -> str:
    value = task.get("task")

    if not isinstance(value, str):
        raise TypeError(
            "Task text must be a string"
        )

    return value


def evaluate_record(
    *,
    source_record: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(source_record["task_id"])
    task_text = task_text_for_task(task)
    source_files = source_files_for_task(task)

    with tempfile.TemporaryDirectory(
        prefix=f"hewn-{task_id}-"
    ) as temp_dir:
        root = copy_fixture(
            task_id,
            Path(temp_dir),
        )

        original_snapshot = snapshot_python_files(
            root
        )

        verification_before = run_pytest(root)

        initial_edits = parse_recorded_edits(
            source_record
        )

        initial_preflight = preflight_exact(
            root=root,
            edits=initial_edits,
        )

        initial_committed = False

        if initial_preflight.valid:
            commit_edits(
                root=root,
                edits=initial_edits,
            )
            initial_committed = True

        after_initial_snapshot = (
            snapshot_python_files(root)
        )

        initial_diff = make_diff(
            original_snapshot,
            after_initial_snapshot,
        )

        initial_syntax_valid = (
            python_syntax_valid(root)
        )

        initial_verification: (
            VerificationResult | None
        ) = None

        if initial_committed:
            initial_verification = run_pytest(
                root
            )

        repair_eligible = bool(
            initial_committed
            and initial_syntax_valid
            and initial_verification is not None
            and not initial_verification.passed
        )

        repair_feedback: (
            dict[str, Any] | None
        ) = None
        repair_feedback_text: str | None = None
        repair_model_response: str | None = None
        repair_model_seconds: float | None = None
        repair_protocol_success: (
            bool | None
        ) = None
        repair_protocol_error: str | None = None
        repair_edits: tuple[Edit, ...] = ()
        repair_preflight: (
            PreflightResult | None
        ) = None
        repair_committed = False

        if (
            repair_eligible
            and initial_verification is not None
        ):
            repair_feedback = (
                normalize_pytest_output(
                    initial_verification.raw_output
                )
            )

            repair_feedback_text = json.dumps(
                repair_feedback,
                indent=2,
            )

            current_source = source_context(
                root=root,
                source_files=source_files,
            )

            model_result = call_model(
                system_prompt=repair_system_prompt(),
                user_prompt=repair_user_prompt(
                    task_text=task_text,
                    feedback=repair_feedback,
                    source=current_source,
                ),
            )

            repair_model_response = (
                model_result.raw_response
            )
            repair_model_seconds = (
                model_result.elapsed_seconds
            )

            try:
                repair_edits = parse_model_response(
                    repair_model_response
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                repair_protocol_success = False
                repair_protocol_error = str(exc)
            else:
                repair_protocol_success = True

                repair_preflight = preflight_exact(
                    root=root,
                    edits=repair_edits,
                )

                if repair_preflight.valid:
                    commit_edits(
                        root=root,
                        edits=repair_edits,
                    )
                    repair_committed = True

        final_snapshot = snapshot_python_files(
            root
        )

        final_diff = make_diff(
            original_snapshot,
            final_snapshot,
        )

        changed_files = count_changed_files(
            original_snapshot,
            final_snapshot,
        )

        added, removed = count_diff_lines(
            final_diff
        )

        syntax_valid = python_syntax_valid(
            root
        )

        final_verification = run_pytest(root)

        outcome = classify_final_outcome(
            initial_preflight=initial_preflight,
            initial_verification=(
                initial_verification
            ),
            repair_eligible=repair_eligible,
            repair_protocol_success=(
                repair_protocol_success
            ),
            repair_preflight=repair_preflight,
            syntax_valid=syntax_valid,
            final_verification=(
                final_verification
            ),
        )

        return {
            "task_id": task_id,
            "category": task.get("category"),
            "task": task_text,
            "source_condition": (
                "normalized_output"
            ),
            "source_result_outcome": (
                source_record.get("outcome")
            ),
            "verification_before": asdict(
                verification_before
            ),
            "initial_edits": [
                asdict(edit)
                for edit in initial_edits
            ],
            "initial_preflight": asdict(
                initial_preflight
            ),
            "initial_committed": (
                initial_committed
            ),
            "initial_diff": initial_diff,
            "initial_syntax_valid": (
                initial_syntax_valid
            ),
            "initial_verification": (
                asdict(initial_verification)
                if initial_verification
                else None
            ),
            "repair_eligible": repair_eligible,
            "repair_feedback": repair_feedback,
            "repair_feedback_text": (
                repair_feedback_text
            ),
            "repair_feedback_characters": (
                len(repair_feedback_text)
                if repair_feedback_text
                else 0
            ),
            "repair_model_response": (
                repair_model_response
            ),
            "repair_model_seconds": (
                repair_model_seconds
            ),
            "repair_protocol_success": (
                repair_protocol_success
            ),
            "repair_protocol_error": (
                repair_protocol_error
            ),
            "repair_edits": [
                asdict(edit)
                for edit in repair_edits
            ],
            "repair_preflight": (
                asdict(repair_preflight)
                if repair_preflight
                else None
            ),
            "repair_committed": (
                repair_committed
            ),
            "final_syntax_valid": syntax_valid,
            "final_verification": asdict(
                final_verification
            ),
            "behavior_success": (
                final_verification.passed
            ),
            "outcome": outcome,
            "changed_files": changed_files,
            "diff_added_lines": added,
            "diff_removed_lines": removed,
            "final_diff": final_diff,
            "new_model_calls": (
                1 if repair_eligible else 0
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

    eligible = [
        record
        for record in records
        if record["repair_eligible"]
    ]

    return {
        "tasks": len(records),
        "behavior_success": sum(
            bool(record["behavior_success"])
            for record in records
        ),
        "initial_success": sum(
            bool(
                record["initial_verification"]
                and record[
                    "initial_verification"
                ]["passed"]
            )
            for record in records
        ),
        "repair_eligible": len(eligible),
        "repair_protocol_success": sum(
            record["repair_protocol_success"]
            is True
            for record in eligible
        ),
        "repair_preflight_success": sum(
            bool(
                record["repair_preflight"]
                and record[
                    "repair_preflight"
                ]["valid"]
            )
            for record in eligible
        ),
        "repair_committed": sum(
            bool(record["repair_committed"])
            for record in eligible
        ),
        "recovered_success": sum(
            record["outcome"]
            == "recovered_success"
            for record in records
        ),
        "new_model_calls": sum(
            int(record["new_model_calls"])
            for record in records
        ),
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
        "Experiment: one normalized "
        "execution-feedback repair iteration"
    )
    print(
        "Initial proposals: "
        "normalized-output-run-001.json"
    )
    print(
        "Repair eligibility: initial batch "
        "committed, syntax valid, pytest failed"
    )
    print(
        "Repair feedback: normalized pytest evidence"
    )
    print(
        "Repair model calls per eligible task: 1"
    )
    print(
        f"Coding model: {MODEL_NAME}"
    )
    print(
        f"Temperature: {TEMPERATURE}"
    )
    print(
        f"Max tokens: {MAX_TOKENS}"
    )
    print(
        f"Context window: {CONTEXT_WINDOW}"
    )
    print(
        "Editing representation: atomic edit_batch"
    )
    print(
        "Underlying primitive: exact replacement"
    )
    print(
        "Verification oracle: pytest"
    )
    print(
        f"Tasks: {len(source_records)}"
    )
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

        result = evaluate_record(
            source_record=source_record,
            task=tasks[task_id],
        )

        records.append(result)

        print(
            f"{task_id}: "
            f"source={result['source_result_outcome']} "
            f"eligible={result['repair_eligible']} "
            f"repair_call="
            f"{result['new_model_calls']} "
            f"outcome={result['outcome']} "
            f"behavior="
            f"{'PASS' if result['behavior_success'] else 'FAIL'}"
        )

        if result["repair_protocol_error"]:
            print(
                "  protocol_error="
                f"{result['repair_protocol_error']}"
            )

        repair_preflight = result[
            "repair_preflight"
        ]

        if (
            repair_preflight is not None
            and not repair_preflight["valid"]
        ):
            print(
                "  application_error="
                f"{repair_preflight['error']}"
            )

    summary = build_summary(records)

    output = {
        "metadata": {
            "module": 7,
            "experiment": (
                "one_normalized_execution_"
                "feedback_repair_iteration"
            ),
            "source_results": str(
                SOURCE_RESULTS_PATH
            ),
            "source_condition": (
                "normalized_output"
            ),
            "initial_model_proposals_reused": True,
            "repair_model": MODEL_NAME,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "context_window": CONTEXT_WINDOW,
            "max_batch_edits": MAX_BATCH_EDITS,
            "repair_calls_per_eligible_task": 1,
            "editing_representation": (
                "atomic edit_batch"
            ),
            "underlying_primitive": (
                "exact replacement"
            ),
            "repair_feedback": (
                "normalized pytest evidence"
            ),
            "verification_oracle": "pytest",
            "grounding_enabled": False,
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
        "Initial success: "
        f"{summary['initial_success']}/"
        f"{summary['tasks']}"
    )
    print(
        "Repair eligible: "
        f"{summary['repair_eligible']}/"
        f"{summary['tasks']}"
    )
    print(
        "Repair protocol success: "
        f"{summary['repair_protocol_success']}/"
        f"{summary['repair_eligible']}"
    )
    print(
        "Repair preflight success: "
        f"{summary['repair_preflight_success']}/"
        f"{summary['repair_eligible']}"
    )
    print(
        "Repair committed: "
        f"{summary['repair_committed']}/"
        f"{summary['repair_eligible']}"
    )
    print(
        "Recovered success: "
        f"{summary['recovered_success']}/"
        f"{summary['repair_eligible']}"
    )
    print(
        "New model calls: "
        f"{summary['new_model_calls']}"
    )
    print(
        f"Outcomes: {summary['outcomes']}"
    )
    print()
    print(f"Results: {RESULTS_PATH}")


if __name__ == "__main__":
    main()