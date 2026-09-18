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

from hewn.agent import (
    Agent,
    AgentLimitError,
    AgentRunResult,
    AgentStagnationError,
)
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionRequirement
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import ModelError
from hewn.tools import (
    ToolCall,
    ToolExecutor,
    ToolRegistry,
    ToolResult,
)
from hewn.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]

MODULE_ROOT = (
    REPO_ROOT
    / "research"
    / "006-code-editing"
)

TASKS_PATH = MODULE_ROOT / "tasks.json"
FIXTURES_ROOT = MODULE_ROOT / "fixtures"
RESULTS_DIR = MODULE_ROOT / "results"

RESULTS_PATH = (
    RESULTS_DIR
    / "replace-text-baseline-run-001.json"
)

CODING_MODEL = (
    "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"
)

TEMPERATURE = 0.0


@dataclass(frozen=True)
class RecordedToolExecution:
    call: ToolCall
    result: ToolResult


class RecordingToolExecutor(ToolExecutor):
    def __init__(
        self,
        registry: ToolRegistry,
    ) -> None:
        super().__init__(registry)
        self.executions: list[
            RecordedToolExecution
        ] = []

    def execute(
        self,
        call: ToolCall,
    ) -> ToolResult:
        result = super().execute(call)

        self.executions.append(
            RecordedToolExecution(
                call=call,
                result=result,
            )
        )

        return result


def load_tasks() -> list[dict[str, Any]]:
    data = json.loads(
        TASKS_PATH.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(data, list):
        raise TypeError(
            "Editing tasks must be a list"
        )

    return data


def snapshot_files(
    root: Path,
) -> dict[str, str]:
    snapshot: dict[str, str] = {}

    for path in sorted(
        root.rglob("*")
    ):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if "__pycache__" in relative.parts:
            continue

        if (
            relative.name.endswith(".pyc")
            or relative.name == ".pytest_cache"
        ):
            continue

        try:
            contents = path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            continue

        snapshot[
            relative.as_posix()
        ] = contents

    return snapshot


def changed_files(
    before: dict[str, str],
    after: dict[str, str],
) -> list[str]:
    return sorted(
        path
        for path in (
            set(before)
            | set(after)
        )
        if before.get(path)
        != after.get(path)
    )


def build_diff(
    before: dict[str, str],
    after: dict[str, str],
) -> str:
    sections: list[str] = []

    for path in changed_files(
        before,
        after,
    ):
        before_text = before.get(
            path,
            "",
        )
        after_text = after.get(
            path,
            "",
        )

        diff = difflib.unified_diff(
            before_text.splitlines(
                keepends=True
            ),
            after_text.splitlines(
                keepends=True
            ),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )

        sections.extend(diff)

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


def source_syntax_valid(
    *,
    workspace_root: Path,
    source_files: list[str],
) -> tuple[bool, str | None]:
    for relative_path in source_files:
        path = (
            workspace_root
            / relative_path
        )

        if not path.exists():
            return (
                False,
                (
                    f"Missing source file: "
                    f"{relative_path}"
                ),
            )

        try:
            source = path.read_text(
                encoding="utf-8"
            )
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
                (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

    return True, None


def run_independent_tests(
    workspace_root: Path,
) -> dict[str, Any]:
    start = perf_counter()

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

    elapsed = perf_counter() - start

    return {
        "passed": (
            completed.returncode == 0
        ),
        "returncode": (
            completed.returncode
        ),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "seconds": elapsed,
    }


def build_task_request(
    *,
    task_text: str,
    workspace_root: Path,
    source_files: list[str],
) -> str:
    sections = [
        (
            "Modify the repository to satisfy "
            "the requested behavior."
        ),
        (
            "Use the available repository tools "
            "to make the change."
        ),
        (
            "Do not modify tests. "
            "Run the tests before finishing."
        ),
        "",
        f"Task:\n{task_text}",
        "",
        (
            "Relevant source is supplied below. "
            "Treat it as the initial repository "
            "state. You may reread files with tools "
            "if needed."
        ),
    ]

    for number, relative_path in enumerate(
        source_files,
        start=1,
    ):
        path = (
            workspace_root
            / relative_path
        )

        contents = path.read_text(
            encoding="utf-8",
        )

        sections.extend(
            [
                "",
                (
                    f"[Source {number}]"
                ),
                (
                    f"path: {relative_path}"
                ),
                contents,
            ]
        )

    return "\n".join(sections)


def serialize_tool_execution(
    execution: RecordedToolExecution,
) -> dict[str, Any]:
    return {
        "name": execution.call.name,
        "arguments": (
            execution.call.arguments
        ),
        "ok": execution.result.ok,
        "output": execution.result.output,
        "error": execution.result.error,
    }


def classify_outcome(
    *,
    replace_attempts: list[
        RecordedToolExecution
    ],
    syntax_valid: bool,
    verification_passed: bool,
    unexpected_files_changed: list[str],
    tests_changed: bool,
) -> str:
    successful_edits = [
        execution
        for execution in replace_attempts
        if execution.result.ok
    ]

    if not replace_attempts:
        return "no_edit"

    if not successful_edits:
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


def run_task(
    *,
    task: dict[str, Any],
    coding_model: LlamaCppModel,
) -> dict[str, Any]:
    task_id = str(task["id"])

    fixture_root = (
        FIXTURES_ROOT
        / task_id
    )

    if not fixture_root.is_dir():
        raise FileNotFoundError(
            
                "Fixture not found: "
                f"{fixture_root}"
            
        )

    source_files = [
        str(path)
        for path in task[
            "source_files"
        ]
    ]

    test_file = str(
        task["test_file"]
    )

    with tempfile.TemporaryDirectory(
        prefix=f"hewn-{task_id}-"
    ) as temporary_directory:
        workspace_root = (
            Path(temporary_directory)
            / task_id
        )

        shutil.copytree(
            fixture_root,
            workspace_root,
        )

        before = snapshot_files(
            workspace_root
        )

        workspace = Workspace(
            workspace_root
        )

        registry = (
            make_builtin_tool_registry(
                workspace,
                repository_index=None,
            )
        )

        executor = (
            RecordingToolExecutor(
                registry
            )
        )

        agent = Agent(
            model=coding_model,
            registry=registry,
            executor=executor,
        )

        request = build_task_request(
            task_text=str(
                task["task"]
            ),
            workspace_root=workspace_root,
            source_files=source_files,
        )

        agent_start = perf_counter()

        agent_result: (
            AgentRunResult | None
        ) = None

        agent_error_type: (
            str | None
        ) = None

        agent_error: (
            str | None
        ) = None

        agent_raw_response: (
            str | None
        ) = None

        metrics = None

        try:
            agent_result = agent.run(
                request,
                completion_requirement=(
                    CompletionRequirement.VERIFIED
                ),
            )

            metrics = (
                agent_result.metrics
            )

        except AgentLimitError as exc:
            agent_error_type = (
                "agent_limit"
            )
            agent_error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            metrics = exc.metrics

        except AgentStagnationError as exc:
            agent_error_type = (
                "agent_stagnation"
            )
            agent_error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            metrics = exc.metrics

        except ModelProtocolError as exc:
            agent_error_type = (
                "protocol"
            )
            agent_error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            agent_raw_response = (
                exc.raw_response
            )

        except ModelError as exc:
            agent_error_type = "model"
            agent_error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

        agent_seconds = (
            perf_counter()
            - agent_start
        )

        after = snapshot_files(
            workspace_root
        )

        changed = changed_files(
            before,
            after,
        )

        diff_text = build_diff(
            before,
            after,
        )

        lines_added, lines_deleted = (
            diff_line_counts(
                diff_text
            )
        )

        syntax_valid, syntax_error = (
            source_syntax_valid(
                workspace_root=(
                    workspace_root
                ),
                source_files=(
                    source_files
                ),
            )
        )

        independent_tests = (
            run_independent_tests(
                workspace_root
            )
        )

        replace_attempts = [
            execution
            for execution
            in executor.executions
            if execution.call.name
            == "replace_text"
        ]

        successful_replace_attempts = [
            execution
            for execution
            in replace_attempts
            if execution.result.ok
        ]

        failed_replace_attempts = [
            execution
            for execution
            in replace_attempts
            if not execution.result.ok
        ]

        allowed_files = set(
            source_files
        )

        unexpected_changed = [
            path
            for path in changed
            if path not in allowed_files
        ]

        tests_changed = (
            test_file in changed
        )

        outcome = classify_outcome(
            replace_attempts=(
                replace_attempts
            ),
            syntax_valid=syntax_valid,
            verification_passed=bool(
                independent_tests[
                    "passed"
                ]
            ),
            unexpected_files_changed=(
                unexpected_changed
            ),
            tests_changed=tests_changed,
        )

        behavior_correct = bool(
            independent_tests[
                "passed"
            ]
        ) and not tests_changed

        return {
            "task_id": task_id,
            "category": (
                task["category"]
            ),
            "task": task["task"],
            "source_files": (
                source_files
            ),
            "test_file": test_file,
            "outcome": outcome,
            "behavior_correct": (
                behavior_correct
            ),
            "agent_finalized": (
                agent_result
                is not None
            ),
            "agent_final_text": (
                agent_result.text
                if agent_result
                is not None
                else None
            ),
            "agent_error_type": (
                agent_error_type
            ),
            "agent_error": (
                agent_error
            ),
            "agent_raw_response": (
                agent_raw_response
            ),
            "agent_seconds": (
                agent_seconds
            ),
            "model_calls": (
                metrics.model_calls
                if metrics is not None
                else None
            ),
            "tool_calls": (
                metrics.tool_calls
                if metrics is not None
                else None
            ),
            "successful_tool_calls": (
                metrics.successful_tool_calls
                if metrics is not None
                else None
            ),
            "failed_tool_calls": (
                metrics.failed_tool_calls
                if metrics is not None
                else None
            ),
            "replace_attempts": (
                len(
                    replace_attempts
                )
            ),
            "successful_replace_attempts": (
                len(
                    successful_replace_attempts
                )
            ),
            "failed_replace_attempts": (
                len(
                    failed_replace_attempts
                )
            ),
            "tool_executions": [
                serialize_tool_execution(
                    execution
                )
                for execution
                in executor.executions
            ],
            "syntax_valid": (
                syntax_valid
            ),
            "syntax_error": (
                syntax_error
            ),
            "verification": (
                independent_tests
            ),
            "files_modified": changed,
            "unexpected_files_modified": (
                unexpected_changed
            ),
            "tests_modified": (
                tests_changed
            ),
            "lines_added": (
                lines_added
            ),
            "lines_deleted": (
                lines_deleted
            ),
            "diff": diff_text,
        }


def main() -> int:
    tasks = load_tasks()

    print(
        f"Coding model: {CODING_MODEL}"
    )
    print(
        f"Temperature: {TEMPERATURE}"
    )
    print(
        "Editing tool: replace_text"
    )
    print(
        "Completion requirement: VERIFIED"
    )
    print(
        "Relevant source: supplied"
    )
    print(
        f"Tasks: {len(tasks)}"
    )
    print(
        "Runs per task: 1"
    )
    print()

    coding_model = LlamaCppModel(
        temperature=TEMPERATURE,
    )

    records: list[
        dict[str, Any]
    ] = []

    started_at = perf_counter()

    for task in tasks:
        print(
            f"{task['id']}: "
            f"{task['category']}"
        )

        record = run_task(
            task=task,
            coding_model=coding_model,
        )

        records.append(record)

        print(
            "  "
            f"outcome={record['outcome']} "
            f"behavior="
            f"{'PASS' if record['behavior_correct'] else 'FAIL'} "
            f"replace="
            f"{record['successful_replace_attempts']}/"
            f"{record['replace_attempts']} "
            f"files={len(record['files_modified'])} "
            f"lines=+{record['lines_added']}"
            f"/-{record['lines_deleted']} "
            f"time={record['agent_seconds']:.2f}s"
        )

        if (
            record["agent_error_type"]
            is not None
        ):
            print(
                "  "
                f"agent_error="
                f"{record['agent_error_type']}"
            )

    total_seconds = (
        perf_counter()
        - started_at
    )

    successes = sum(
        bool(
            record[
                "behavior_correct"
            ]
        )
        for record in records
    )

    finalized = sum(
        bool(
            record[
                "agent_finalized"
            ]
        )
        for record in records
    )

    tasks_with_edit_attempt = sum(
        int(
            record[
                "replace_attempts"
            ]
        )
        > 0
        for record in records
    )

    tasks_with_applied_edit = sum(
        int(
            record[
                "successful_replace_attempts"
            ]
        )
        > 0
        for record in records
    )

    total_replace_attempts = sum(
        int(
            record[
                "replace_attempts"
            ]
        )
        for record in records
    )

    successful_replace_attempts = sum(
        int(
            record[
                "successful_replace_attempts"
            ]
        )
        for record in records
    )

    failed_replace_attempts = sum(
        int(
            record[
                "failed_replace_attempts"
            ]
        )
        for record in records
    )

    outcome_counts: dict[str, int] = {}

    for record in records:
        outcome = str(
            record["outcome"]
        )

        outcome_counts[outcome] = (
            outcome_counts.get(
                outcome,
                0,
            )
            + 1
        )

    output = {
        "experiment": (
            "module_6_replace_text_baseline"
        ),
        "configuration": {
            "coding_model": (
                CODING_MODEL
            ),
            "temperature": (
                TEMPERATURE
            ),
            "editing_tool": (
                "replace_text"
            ),
            "completion_requirement": (
                "VERIFIED"
            ),
            "source_supplied": True,
            "task_count": (
                len(tasks)
            ),
            "runs_per_task": 1,
            "repeated_trials": False,
        },
        "summary": {
            "behavior_successes": (
                successes
            ),
            "agent_finalizations": (
                finalized
            ),
            "tasks_with_edit_attempt": (
                tasks_with_edit_attempt
            ),
            "tasks_with_applied_edit": (
                tasks_with_applied_edit
            ),
            "replace_attempts": (
                total_replace_attempts
            ),
            "successful_replace_attempts": (
                successful_replace_attempts
            ),
            "failed_replace_attempts": (
                failed_replace_attempts
            ),
            "outcomes": (
                outcome_counts
            ),
            "total_seconds": (
                total_seconds
            ),
        },
        "records": records,
    }

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
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
        f"Behavior success: "
        f"{successes}/{len(tasks)}"
    )
    print(
        f"Agent finalized: "
        f"{finalized}/{len(tasks)}"
    )
    print(
        "Tasks with edit attempt: "
        f"{tasks_with_edit_attempt}/"
        f"{len(tasks)}"
    )
    print(
        "Tasks with applied edit: "
        f"{tasks_with_applied_edit}/"
        f"{len(tasks)}"
    )
    print(
        "replace_text attempts: "
        f"{successful_replace_attempts}/"
        f"{total_replace_attempts} applied, "
        f"{failed_replace_attempts} rejected"
    )
    print(
        f"Outcomes: {outcome_counts}"
    )
    print(
        f"Total wall time: "
        f"{total_seconds:.2f}s"
    )
    print()
    print(
        f"Results: {RESULTS_PATH}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )