from __future__ import annotations

import ast
import difflib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from hewn.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "research" / "007-execution-feedback"

TASKS_PATH = MODULE_ROOT / "tasks.json"
FIXTURES_ROOT = MODULE_ROOT / "fixtures"
RESULTS_DIR = MODULE_ROOT / "results"

CONDITION = "failure_signal"

RESULTS_PATH = (
    RESULTS_DIR
    / "failure-signal-run-001.json"
)

CODING_MODEL = "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"

BASE_URL = "http://127.0.0.1:8080"
TEMPERATURE = 0.0
MAX_TOKENS = 512
TIMEOUT_SECONDS = 120.0

MAX_BATCH_EDITS = 6


@dataclass(frozen=True)
class BatchEdit:
    path: str
    old: str
    new: str


@dataclass(frozen=True)
class BatchProposal:
    raw_response: str
    edits: tuple[BatchEdit, ...]
    protocol_error: str | None


@dataclass(frozen=True)
class PreflightResult:
    valid: bool
    failed_edit_index: int | None
    error: str | None


def load_tasks() -> list[dict[str, Any]]:
    data = json.loads(
        TASKS_PATH.read_text(encoding="utf-8")
    )

    if not isinstance(data, list):
        raise TypeError("Execution-feedback tasks must be a list")

    return data


def snapshot_files(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if "__pycache__" in relative.parts:
            continue

        if ".pytest_cache" in relative.parts:
            continue

        if relative.name.endswith(".pyc"):
            continue

        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        snapshot[relative.as_posix()] = contents

    return snapshot


def changed_files(
    before: dict[str, str],
    after: dict[str, str],
) -> list[str]:
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def build_diff(
    before: dict[str, str],
    after: dict[str, str],
) -> str:
    sections: list[str] = []

    for path in changed_files(before, after):
        before_text = before.get(path, "")
        after_text = after.get(path, "")

        sections.extend(
            difflib.unified_diff(
                before_text.splitlines(keepends=True),
                after_text.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )

    return "".join(sections)


def diff_line_counts(
    diff_text: str,
) -> tuple[int, int]:
    added = 0
    deleted = 0

    for line in diff_text.splitlines():
        if line.startswith("+++"):
            continue

        if line.startswith("---"):
            continue

        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            deleted += 1

    return added, deleted


def current_sources(
    *,
    workspace_root: Path,
    source_files: list[str],
) -> str:
    sections: list[str] = []

    for number, relative_path in enumerate(
        source_files,
        start=1,
    ):
        path = workspace_root / relative_path

        if path.exists():
            contents = path.read_text(encoding="utf-8")
        else:
            contents = "<missing file>"

        sections.extend(
            [
                f"[Source {number}]",
                f"path: {relative_path}",
                contents,
                "",
            ]
        )

    return "\n".join(sections)


def build_system_prompt() -> str:
    return f"""You are the repair model inside Hewn.

The current implementation has already been verified and is incorrect.

Your only job is to propose the complete code repair as a batch of exact
text replacements.

Respond with exactly one JSON object using this shape:

{{
  "type": "edit_batch",
  "edits": [
    {{
      "path": "relative/path.py",
      "old": "exact existing text",
      "new": "replacement text"
    }}
  ]
}}

Rules:

- Return between 1 and {MAX_BATCH_EDITS} edits.
- Return all edits needed to complete the repair.
- Each edit uses exact text replacement.
- "old" must match repository text exactly.
- "old" must occur exactly once at the point that edit is applied.
- Edits are evaluated in array order.
- A later edit may target text produced by an earlier edit.
- For insertion, use a unique existing anchor.
- For multiple locations, emit multiple edits.
- For multiple files, emit every required edit.
- Do not modify tests.
- Do not return a final answer.
- Do not use Markdown fences.
- Do not include explanations.
- Return exactly one JSON object.
"""


def build_user_prompt(
    *,
    task_text: str,
    workspace_root: Path,
    source_files: list[str],
) -> str:
    return "\n".join(
        [
            "Repair the current implementation.",
            "",
            f"Task:\n{task_text}",
            "",
            "Verification result:",
            "FAILED",
            "",
            (
                "No additional execution details are "
                "available in this condition."
            ),
            "",
            "Relevant source:",
            current_sources(
                workspace_root=workspace_root,
                source_files=source_files,
            ),
        ]
    )


def extract_content(body: str) -> str:
    try:
        payload: Any = json.loads(body)
        content = payload["choices"][0]["message"]["content"]
    except (
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise RuntimeError(
            "llama.cpp returned an invalid chat response"
        ) from exc

    if not isinstance(content, str):
        raise TypeError(
            "llama.cpp returned non-text assistant content"
        )

    return content


def call_llama(
    *,
    messages: list[dict[str, str]],
) -> str:
    payload = {
        "model": "local",
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    request = Request(
        f"{BASE_URL}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(
            f"llama.cpp returned HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"Could not reach llama.cpp: {exc.reason}"
        ) from exc

    return extract_content(body)


def parse_batch_proposal(
    raw_response: str,
) -> BatchProposal:
    try:
        payload: Any = json.loads(raw_response)
    except json.JSONDecodeError:
        return BatchProposal(
            raw_response=raw_response,
            edits=(),
            protocol_error="Model response is not valid JSON",
        )

    if not isinstance(payload, dict):
        return BatchProposal(
            raw_response=raw_response,
            edits=(),
            protocol_error=(
                "Model response must be a JSON object"
            ),
        )

    if set(payload) != {"type", "edits"}:
        return BatchProposal(
            raw_response=raw_response,
            edits=(),
            protocol_error=(
                "Batch response has unexpected fields"
            ),
        )

    if payload["type"] != "edit_batch":
        return BatchProposal(
            raw_response=raw_response,
            edits=(),
            protocol_error=(
                "Response type must be edit_batch"
            ),
        )

    raw_edits = payload["edits"]

    if not isinstance(raw_edits, list):
        return BatchProposal(
            raw_response=raw_response,
            edits=(),
            protocol_error="edits must be an array",
        )

    if not 1 <= len(raw_edits) <= MAX_BATCH_EDITS:
        return BatchProposal(
            raw_response=raw_response,
            edits=(),
            protocol_error=(
                "edit batch must contain between "
                f"1 and {MAX_BATCH_EDITS} edits"
            ),
        )

    parsed: list[BatchEdit] = []

    for index, raw_edit in enumerate(raw_edits):
        if not isinstance(raw_edit, dict):
            return BatchProposal(
                raw_response=raw_response,
                edits=(),
                protocol_error=(
                    f"edit {index} must be an object"
                ),
            )

        if set(raw_edit) != {"path", "old", "new"}:
            return BatchProposal(
                raw_response=raw_response,
                edits=(),
                protocol_error=(
                    f"edit {index} has unexpected fields"
                ),
            )

        path = raw_edit["path"]
        old = raw_edit["old"]
        new = raw_edit["new"]

        if not isinstance(path, str):
            return BatchProposal(
                raw_response=raw_response,
                edits=(),
                protocol_error=(
                    f"edit {index} path must be a string"
                ),
            )

        if not isinstance(old, str):
            return BatchProposal(
                raw_response=raw_response,
                edits=(),
                protocol_error=(
                    f"edit {index} old must be a string"
                ),
            )

        if not isinstance(new, str):
            return BatchProposal(
                raw_response=raw_response,
                edits=(),
                protocol_error=(
                    f"edit {index} new must be a string"
                ),
            )

        if not path:
            return BatchProposal(
                raw_response=raw_response,
                edits=(),
                protocol_error=(
                    f"edit {index} path must not be empty"
                ),
            )

        if not old:
            return BatchProposal(
                raw_response=raw_response,
                edits=(),
                protocol_error=(
                    f"edit {index} old must not be empty"
                ),
            )

        parsed.append(
            BatchEdit(
                path=path,
                old=old,
                new=new,
            )
        )

    return BatchProposal(
        raw_response=raw_response,
        edits=tuple(parsed),
        protocol_error=None,
    )


def validate_relative_path(
    *,
    workspace: Workspace,
    relative_path: str,
) -> Path:
    path = workspace.resolve(relative_path)

    if not path.exists():
        raise ValueError(
            f"File does not exist: {relative_path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Path is not a file: {relative_path}"
        )

    return path


def preflight_batch(
    *,
    workspace: Workspace,
    edits: tuple[BatchEdit, ...],
) -> tuple[PreflightResult, dict[Path, str]]:
    simulated: dict[Path, str] = {}

    for index, edit in enumerate(edits):
        try:
            path = validate_relative_path(
                workspace=workspace,
                relative_path=edit.path,
            )
        except ValueError as exc:
            return (
                PreflightResult(
                    valid=False,
                    failed_edit_index=index,
                    error=str(exc),
                ),
                {},
            )

        if edit.old == edit.new:
            return (
                PreflightResult(
                    valid=False,
                    failed_edit_index=index,
                    error=(
                        "Replacement is a no-op: old and "
                        "new text are identical"
                    ),
                ),
                {},
            )

        if path not in simulated:
            try:
                simulated[path] = path.read_text(
                    encoding="utf-8"
                )
            except UnicodeDecodeError:
                return (
                    PreflightResult(
                        valid=False,
                        failed_edit_index=index,
                        error=(
                            "File is not valid UTF-8: "
                            f"{edit.path}"
                        ),
                    ),
                    {},
                )

        contents = simulated[path]
        occurrences = contents.count(edit.old)

        if occurrences == 0:
            return (
                PreflightResult(
                    valid=False,
                    failed_edit_index=index,
                    error="Text to replace was not found",
                ),
                {},
            )

        if occurrences > 1:
            return (
                PreflightResult(
                    valid=False,
                    failed_edit_index=index,
                    error=(
                        "Text to replace occurs more "
                        "than once"
                    ),
                ),
                {},
            )

        simulated[path] = contents.replace(
            edit.old,
            edit.new,
            1,
        )

    return (
        PreflightResult(
            valid=True,
            failed_edit_index=None,
            error=None,
        ),
        simulated,
    )


def commit_simulated(
    simulated: dict[Path, str],
) -> None:
    for path, contents in simulated.items():
        path.write_text(
            contents,
            encoding="utf-8",
        )


def source_syntax_valid(
    *,
    workspace_root: Path,
    source_files: list[str],
) -> tuple[bool, str | None]:
    for relative_path in source_files:
        path = workspace_root / relative_path

        if not path.exists():
            return (
                False,
                f"Missing source file: {relative_path}",
            )

        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(
                source,
                filename=relative_path,
            )
        except (
            UnicodeDecodeError,
            SyntaxError,
        ) as exc:
            return (
                False,
                f"{type(exc).__name__}: {exc}",
            )

    return True, None


def run_verification(
    workspace_root: Path,
) -> dict[str, Any]:
    started = perf_counter()

    completed = subprocess.run(
        [
            "python",
            "-B",
            "-m",
            "pytest",
            "-q",
        ],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60.0,
    )

    stdout = completed.stdout
    stderr = completed.stderr

    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "raw_output": stdout + stderr,
        "raw_output_characters": len(stdout + stderr),
        "raw_output_lines": len(
            (stdout + stderr).splitlines()
        ),
        "seconds": perf_counter() - started,
    }


def classify_outcome(
    *,
    model_failure: bool,
    protocol_failure: bool,
    preflight_valid: bool,
    syntax_valid: bool,
    verification_passed: bool,
    tests_changed: bool,
    unexpected_files_changed: list[str],
) -> str:
    if model_failure:
        return "model_failure"

    if protocol_failure:
        return "protocol_failure"

    if not preflight_valid:
        return "application_failure"

    if not syntax_valid:
        return "invalid_code"

    if tests_changed:
        return "verification_failure"

    if not verification_passed:
        return "verification_failure"

    if unexpected_files_changed:
        return "success_with_extra_changes"

    return "success"


def serialize_edits(
    proposal: BatchProposal | None,
) -> list[dict[str, str]]:
    if proposal is None:
        return []

    return [
        {
            "path": edit.path,
            "old": edit.old,
            "new": edit.new,
        }
        for edit in proposal.edits
    ]


def run_task(
    task: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(task["id"])
    fixture_root = FIXTURES_ROOT / task_id

    if not fixture_root.is_dir():
        raise FileNotFoundError(
            f"Fixture not found: {fixture_root}"
        )

    source_files = [
        str(path)
        for path in task["source_files"]
    ]
    test_file = str(task["test_file"])

    with tempfile.TemporaryDirectory(
        prefix=f"hewn-feedback-{task_id}-"
    ) as temporary_directory:
        workspace_root = (
            Path(temporary_directory) / task_id
        )

        shutil.copytree(
            fixture_root,
            workspace_root,
        )

        workspace = Workspace(workspace_root)

        before = snapshot_files(workspace_root)

        # Establish the actual failing execution state before
        # asking the model for a repair.
        verification_before = run_verification(
            workspace_root
        )

        if verification_before["passed"]:
            raise RuntimeError(
                f"{task_id} is not a failing fixture"
            )

        feedback_text = "FAILED"

        model_failure = False
        model_error: str | None = None
        proposal: BatchProposal | None = None
        model_seconds = 0.0

        messages = [
            {
                "role": "system",
                "content": build_system_prompt(),
            },
            {
                "role": "user",
                "content": build_user_prompt(
                    task_text=str(task["task"]),
                    workspace_root=workspace_root,
                    source_files=source_files,
                ),
            },
        ]

        try:
            started = perf_counter()

            raw_response = call_llama(
                messages=messages
            )

            model_seconds = (
                perf_counter() - started
            )

            proposal = parse_batch_proposal(
                raw_response
            )
        except (RuntimeError, TypeError) as exc:
            model_failure = True
            model_error = (
                f"{type(exc).__name__}: {exc}"
            )

        preflight = PreflightResult(
            valid=False,
            failed_edit_index=None,
            error=None,
        )
        simulated: dict[Path, str] = {}

        if (
            not model_failure
            and proposal is not None
            and proposal.protocol_error is None
        ):
            preflight, simulated = preflight_batch(
                workspace=workspace,
                edits=proposal.edits,
            )

        protocol_failure = (
            not model_failure
            and proposal is not None
            and proposal.protocol_error is not None
        )

        committed = False

        if (
            not model_failure
            and not protocol_failure
            and preflight.valid
        ):
            commit_simulated(simulated)
            committed = True

        after = snapshot_files(workspace_root)

        changed = changed_files(
            before,
            after,
        )
        diff_text = build_diff(
            before,
            after,
        )

        lines_added, lines_deleted = (
            diff_line_counts(diff_text)
        )

        syntax_valid, syntax_error = (
            source_syntax_valid(
                workspace_root=workspace_root,
                source_files=source_files,
            )
        )

        verification_after = run_verification(
            workspace_root
        )

        allowed_files = set(source_files)

        unexpected_changed = [
            path
            for path in changed
            if path not in allowed_files
        ]

        tests_changed = test_file in changed

        behavior_correct = (
            bool(verification_after["passed"])
            and not tests_changed
        )

        outcome = classify_outcome(
            model_failure=model_failure,
            protocol_failure=protocol_failure,
            preflight_valid=preflight.valid,
            syntax_valid=syntax_valid,
            verification_passed=bool(
                verification_after["passed"]
            ),
            tests_changed=tests_changed,
            unexpected_files_changed=(
                unexpected_changed
            ),
        )

        protocol_error = (
            proposal.protocol_error
            if proposal is not None
            else None
        )

        raw_model_response = (
            proposal.raw_response
            if proposal is not None
            else None
        )

        return {
            "task_id": task_id,
            "category": task["category"],
            "task": task["task"],
            "condition": CONDITION,
            "source_files": source_files,
            "test_file": test_file,
            "feedback_text": feedback_text,
            "feedback_characters": len(
                feedback_text
            ),
            "feedback_lines": len(
                feedback_text.splitlines()
            ),
            "verification_before": (
                verification_before
            ),
            "model_failure": model_failure,
            "model_error": model_error,
            "protocol_error": protocol_error,
            "raw_model_response": (
                raw_model_response
            ),
            "proposed_edits": serialize_edits(
                proposal
            ),
            "preflight_valid": preflight.valid,
            "failed_edit_index": (
                preflight.failed_edit_index
            ),
            "application_error": (
                preflight.error
            ),
            "committed": committed,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "verification_after": (
                verification_after
            ),
            "behavior_correct": behavior_correct,
            "files_modified": changed,
            "unexpected_files_modified": (
                unexpected_changed
            ),
            "tests_modified": tests_changed,
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "diff": diff_text,
            "outcome": outcome,
            "model_seconds": model_seconds,
        }


def main() -> int:
    tasks = load_tasks()

    print(f"Condition: {CONDITION}")
    print(f"Coding model: {CODING_MODEL}")
    print(f"Temperature: {TEMPERATURE}")
    print(f"Max tokens: {MAX_TOKENS}")
    print("Context window: 4096")
    print("Editing representation: atomic edit_batch")
    print("Underlying primitive: exact replace_text")
    print(
        f"Maximum edits per batch: {MAX_BATCH_EDITS}"
    )
    print("Model calls per task: 1")
    print("Feedback exposed to model: FAILED only")
    print("Verification oracle: pytest")
    print("Runs per task: 1")
    print(f"Tasks: {len(tasks)}")
    print()

    records: list[dict[str, Any]] = []
    started = perf_counter()

    for task in tasks:
        record = run_task(task)
        records.append(record)

        print(
            f"{record['task_id']}: "
            f"{record['category']}"
        )

        print(
            "  "
            f"outcome={record['outcome']} "
            f"behavior="
            f"{'PASS' if record['behavior_correct'] else 'FAIL'} "
            f"protocol="
            f"{'PASS' if record['protocol_error'] is None and not record['model_failure'] else 'FAIL'} "
            f"preflight="
            f"{'PASS' if record['preflight_valid'] else 'FAIL'} "
            f"committed={record['committed']} "
            f"files={len(record['files_modified'])} "
            f"lines=+{record['lines_added']}"
            f"/-{record['lines_deleted']} "
            f"time={record['model_seconds']:.2f}s"
        )

        if record["application_error"] is not None:
            print(
                "  application_error="
                f"{record['application_error']}"
            )

        if record["model_error"] is not None:
            print(
                "  model_error="
                f"{record['model_error']}"
            )

    total_seconds = perf_counter() - started

    behavior_successes = sum(
        bool(record["behavior_correct"])
        for record in records
    )

    protocol_successes = sum(
        not bool(record["model_failure"])
        and record["protocol_error"] is None
        for record in records
    )

    preflight_successes = sum(
        bool(record["preflight_valid"])
        for record in records
    )

    committed_batches = sum(
        bool(record["committed"])
        for record in records
    )

    outcome_counts: dict[str, int] = {}

    for record in records:
        outcome = str(record["outcome"])
        outcome_counts[outcome] = (
            outcome_counts.get(outcome, 0) + 1
        )

    output = {
        "experiment": (
            "module_7_failure_signal"
        ),
        "configuration": {
            "condition": CONDITION,
            "coding_model": CODING_MODEL,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "context_window": 4096,
            "editing_representation": (
                "atomic_edit_batch"
            ),
            "underlying_primitive": (
                "exact_replace_text"
            ),
            "max_batch_edits": MAX_BATCH_EDITS,
            "model_calls_per_task": 1,
            "feedback": "FAILED",
            "verification": "pytest",
            "task_count": len(tasks),
            "runs_per_task": 1,
            "repeated_trials": False,
        },
        "summary": {
            "behavior_successes": (
                behavior_successes
            ),
            "protocol_successes": (
                protocol_successes
            ),
            "preflight_successes": (
                preflight_successes
            ),
            "committed_batches": (
                committed_batches
            ),
            "outcomes": outcome_counts,
            "total_seconds": total_seconds,
        },
        "records": records,
    }

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if RESULTS_PATH.exists():
        raise FileExistsError(
            "Refusing to overwrite existing "
            f"experiment result: {RESULTS_PATH}"
        )

    RESULTS_PATH.write_text(
        json.dumps(
            output,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("Summary")
    print(
        "Behavior success: "
        f"{behavior_successes}/{len(tasks)}"
    )
    print(
        "Strict protocol success: "
        f"{protocol_successes}/{len(tasks)}"
    )
    print(
        "Preflight success: "
        f"{preflight_successes}/{len(tasks)}"
    )
    print(
        "Committed batches: "
        f"{committed_batches}/{len(tasks)}"
    )
    print(f"Outcomes: {outcome_counts}")
    print(
        "Total wall time: "
        f"{total_seconds:.2f}s"
    )
    print()
    print(f"Results: {RESULTS_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())