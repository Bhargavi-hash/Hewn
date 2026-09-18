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

from hewn.builtin_tools import make_builtin_tool_registry
from hewn.model_protocol import (
    ModelProtocolError,
    parse_model_response,
)
from hewn.models import ModelError
from hewn.tools import (
    ToolCall,
    ToolExecutor,
    ToolRegistry,
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
    / "controlled-replace-text-run-001.json"
)

CODING_MODEL = (
    "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"
)

BASE_URL = "http://127.0.0.1:8080"
TEMPERATURE = 0.0
MAX_TOKENS = 256
TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class ModelObservation:
    raw_response: str
    parsed_call: ToolCall | None
    protocol_error: str | None


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
                    "Missing source file: "
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

    elapsed = (
        perf_counter()
        - start
    )

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
            "Produce the code edit required to satisfy "
            "the task."
        ),
        "",
        f"Task:\n{task_text}",
        "",
        (
            "The relevant repository source is supplied "
            "below."
        ),
        (
            "You must express the modification using "
            "the replace_text action."
        ),
        (
            "Do not return a final answer. "
            "Do not explain the change."
        ),
    ]

    for number, relative_path in enumerate(
        source_files,
        start=1,
    ):
        contents = (
            workspace_root
            / relative_path
        ).read_text(
            encoding="utf-8"
        )

        sections.extend(
            [
                "",
                f"[Source {number}]",
                f"path: {relative_path}",
                contents,
            ]
        )

    return "\n".join(sections)


def make_replace_registry(
    workspace: Workspace,
) -> ToolRegistry:
    full_registry = (
        make_builtin_tool_registry(
            workspace,
            repository_index=None,
        )
    )

    replace_definition = next(
        definition
        for definition
        in full_registry.definitions()
        if definition.name == "replace_text"
    )

    registry = ToolRegistry()

    registry.register(
        replace_definition
    )

    return registry


def build_system_prompt(
    registry: ToolRegistry,
) -> str:
    replace_definition = next(
        definition
        for definition
        in registry.definitions()
        if definition.name == "replace_text"
    )

    schema = json.dumps(
        replace_definition.input_schema,
        sort_keys=True,
    )

    return (
        "You are the editing-action model inside "
        "Hewn, a coding agent.\n"
        "Your only job is to propose one code edit.\n"
        "Exactly one action is permitted: "
        "replace_text.\n\n"
        "Respond with exactly one JSON object using "
        "this shape:\n"
        '{"type":"tool_call","name":"replace_text",'
        '"arguments":{"path":"FILE","old":"OLD_TEXT",'
        '"new":"NEW_TEXT"}}\n\n'
        "The arguments must satisfy this schema:\n"
        f"{schema}\n\n"
        "The old text must match repository text "
        "exactly and must occur exactly once.\n"
        "Return exactly one JSON object and no "
        "Markdown fences, explanation, or additional "
        "text."
    )


def extract_content(
    body: str,
) -> str:
    try:
        payload: Any = json.loads(
            body
        )

        content = (
            payload["choices"][0]
            ["message"]["content"]
        )

    except (
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise ModelError(
            "llama.cpp returned an invalid chat response"
        ) from exc

    if not isinstance(
        content,
        str,
    ):
        raise ModelError(
            "llama.cpp returned non-text assistant content"
        )

    return content


def request_model_edit(
    *,
    task_request: str,
    registry: ToolRegistry,
) -> ModelObservation:
    payload = {
        "model": "local",
        "messages": [
            {
                "role": "system",
                "content": build_system_prompt(
                    registry
                ),
            },
            {
                "role": "user",
                "content": task_request,
            },
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    request = Request(
        f"{BASE_URL}/v1/chat/completions",
        data=json.dumps(
            payload
        ).encode("utf-8"),
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
            body = (
                response.read().decode(
                    "utf-8"
                )
            )

    except HTTPError as exc:
        raise ModelError(
            
                "llama.cpp returned HTTP "
                f"{exc.code}"
            
        ) from exc

    except URLError as exc:
        raise ModelError(
            
                "Could not reach llama.cpp: "
                f"{exc.reason}"
            
        ) from exc

    raw_response = extract_content(
        body
    )

    try:
        parsed = parse_model_response(
            raw_response
        )

    except ModelProtocolError as exc:
        return ModelObservation(
            raw_response=(
                exc.raw_response
            ),
            parsed_call=None,
            protocol_error=(
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )

    if not isinstance(
        parsed,
        ToolCall,
    ):
        return ModelObservation(
            raw_response=raw_response,
            parsed_call=None,
            protocol_error=(
                "Model returned a final response "
                "instead of replace_text"
            ),
        )

    if parsed.name != "replace_text":
        return ModelObservation(
            raw_response=raw_response,
            parsed_call=None,
            protocol_error=(
                "Model returned an unexpected "
                f"tool: {parsed.name}"
            ),
        )

    return ModelObservation(
        raw_response=raw_response,
        parsed_call=parsed,
        protocol_error=None,
    )


def classify_outcome(
    *,
    model_observation: ModelObservation | None,
    application_attempted: bool,
    application_succeeded: bool,
    syntax_valid: bool,
    verification_passed: bool,
    tests_changed: bool,
    unexpected_files_changed: list[str],
    model_error: str | None,
) -> str:
    if model_error is not None:
        return "model_failure"

    if (
        model_observation is None
        or model_observation.protocol_error
        is not None
    ):
        return "protocol_failure"

    if not application_attempted:
        return "no_edit"

    if not application_succeeded:
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
    task: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(
        task["id"]
    )

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
        prefix=f"hewn-controlled-{task_id}-"
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

        registry = make_replace_registry(
            workspace
        )

        executor = ToolExecutor(
            registry
        )

        task_request = build_task_request(
            task_text=str(
                task["task"]
            ),
            workspace_root=workspace_root,
            source_files=source_files,
        )

        start = perf_counter()

        observation: (
            ModelObservation | None
        ) = None

        model_error: (
            str | None
        ) = None

        application_attempted = False
        application_succeeded = False

        application_output: (
            str | None
        ) = None

        application_error: (
            str | None
        ) = None

        try:
            observation = (
                request_model_edit(
                    task_request=(
                        task_request
                    ),
                    registry=registry,
                )
            )

            if (
                observation.parsed_call
                is not None
            ):
                application_attempted = True

                result = executor.execute(
                    observation.parsed_call
                )

                application_succeeded = (
                    result.ok
                )

                application_output = (
                    result.output
                )

                application_error = (
                    result.error
                )

        except ModelError as exc:
            model_error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

        model_and_application_seconds = (
            perf_counter()
            - start
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
                source_files=source_files,
            )
        )

        independent_tests = (
            run_independent_tests(
                workspace_root
            )
        )

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
            model_observation=observation,
            application_attempted=(
                application_attempted
            ),
            application_succeeded=(
                application_succeeded
            ),
            syntax_valid=syntax_valid,
            verification_passed=bool(
                independent_tests[
                    "passed"
                ]
            ),
            tests_changed=tests_changed,
            unexpected_files_changed=(
                unexpected_changed
            ),
            model_error=model_error,
        )

        behavior_correct = (
            bool(
                independent_tests[
                    "passed"
                ]
            )
            and not tests_changed
        )

        parsed_call = (
            observation.parsed_call
            if observation is not None
            else None
        )

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
            "raw_model_response": (
                observation.raw_response
                if observation is not None
                else None
            ),
            "protocol_error": (
                observation.protocol_error
                if observation is not None
                else None
            ),
            "model_error": (
                model_error
            ),
            "parsed_tool_name": (
                parsed_call.name
                if parsed_call is not None
                else None
            ),
            "parsed_arguments": (
                parsed_call.arguments
                if parsed_call is not None
                else None
            ),
            "application_attempted": (
                application_attempted
            ),
            "application_succeeded": (
                application_succeeded
            ),
            "application_output": (
                application_output
            ),
            "application_error": (
                application_error
            ),
            "syntax_valid": (
                syntax_valid
            ),
            "syntax_error": (
                syntax_error
            ),
            "verification": (
                independent_tests
            ),
            "files_modified": (
                changed
            ),
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
            "diff": (
                diff_text
            ),
            "model_and_application_seconds": (
                model_and_application_seconds
            ),
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
        f"Max tokens: {MAX_TOKENS}"
    )
    print(
        "Permitted action: replace_text only"
    )
    print(
        "Final response: not permitted"
    )
    print(
        "Relevant source: supplied"
    )
    print(
        "Verification: evaluator-side"
    )
    print(
        f"Tasks: {len(tasks)}"
    )
    print(
        "Runs per task: 1"
    )
    print()

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
            task
        )

        records.append(
            record
        )

        print(
            "  "
            f"outcome={record['outcome']} "
            f"behavior="
            f"{'PASS' if record['behavior_correct'] else 'FAIL'} "
            f"attempted="
            f"{record['application_attempted']} "
            f"applied="
            f"{record['application_succeeded']} "
            f"files="
            f"{len(record['files_modified'])} "
            f"lines="
            f"+{record['lines_added']}"
            f"/-{record['lines_deleted']} "
            f"time="
            f"{record['model_and_application_seconds']:.2f}s"
        )

        if (
            record["protocol_error"]
            is not None
        ):
            print(
                "  protocol_error=yes"
            )

        if (
            record["application_error"]
            is not None
        ):
            print(
                "  application_error="
                f"{record['application_error']}"
            )

    total_seconds = (
        perf_counter()
        - started_at
    )

    behavior_successes = sum(
        bool(
            record[
                "behavior_correct"
            ]
        )
        for record in records
    )

    protocol_successes = sum(
        (
            record[
                "protocol_error"
            ]
            is None
            and record[
                "model_error"
            ]
            is None
        )
        for record in records
    )

    edit_attempts = sum(
        bool(
            record[
                "application_attempted"
            ]
        )
        for record in records
    )

    applied_edits = sum(
        bool(
            record[
                "application_succeeded"
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
            "module_6_controlled_replace_text"
        ),
        "configuration": {
            "coding_model": (
                CODING_MODEL
            ),
            "temperature": (
                TEMPERATURE
            ),
            "max_tokens": (
                MAX_TOKENS
            ),
            "permitted_actions": [
                "replace_text",
            ],
            "final_response_permitted": (
                False
            ),
            "source_supplied": True,
            "verification": (
                "evaluator_side"
            ),
            "task_count": (
                len(tasks)
            ),
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
            "tasks_with_edit_attempt": (
                edit_attempts
            ),
            "tasks_with_applied_edit": (
                applied_edits
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
        f"{behavior_successes}/"
        f"{len(tasks)}"
    )
    print(
        "Strict protocol success: "
        f"{protocol_successes}/"
        f"{len(tasks)}"
    )
    print(
        "Tasks with edit attempt: "
        f"{edit_attempts}/"
        f"{len(tasks)}"
    )
    print(
        "Tasks with applied edit: "
        f"{applied_edits}/"
        f"{len(tasks)}"
    )
    print(
        f"Outcomes: {outcome_counts}"
    )
    print(
        "Total wall time: "
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