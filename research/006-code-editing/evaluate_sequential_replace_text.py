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
from hewn.model_protocol import ModelProtocolError
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry
from hewn.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "research" / "006-code-editing"

TASKS_PATH = MODULE_ROOT / "tasks.json"
FIXTURES_ROOT = MODULE_ROOT / "fixtures"
RESULTS_DIR = MODULE_ROOT / "results"
RESULTS_PATH = RESULTS_DIR / "sequential-replace-text-run-001.json"

CODING_MODEL = "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"

BASE_URL = "http://127.0.0.1:8080"
TEMPERATURE = 0.0
MAX_TOKENS = 256
TIMEOUT_SECONDS = 120.0

MAX_EDIT_ATTEMPTS = 4


@dataclass(frozen=True)
class SequentialAction:
    raw_response: str
    kind: str
    call: ToolCall | None
    protocol_error: str | None


def load_tasks() -> list[dict[str, Any]]:
    data = json.loads(
        TASKS_PATH.read_text(encoding="utf-8")
    )

    if not isinstance(data, list):
        raise TypeError("Editing tasks must be a list")

    return data


def snapshot_files(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if "__pycache__" in relative.parts:
            continue

        if relative.name.endswith(".pyc"):
            continue

        if ".pytest_cache" in relative.parts:
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

        diff = difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
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

    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "seconds": perf_counter() - start,
    }


def make_replace_registry(
    workspace: Workspace,
) -> ToolRegistry:
    full_registry = make_builtin_tool_registry(
        workspace,
        repository_index=None,
    )

    replace_definition = next(
        definition
        for definition in full_registry.definitions()
        if definition.name == "replace_text"
    )

    registry = ToolRegistry()
    registry.register(replace_definition)

    return registry


def replace_schema(
    registry: ToolRegistry,
) -> dict[str, Any]:
    definition = next(
        definition
        for definition in registry.definitions()
        if definition.name == "replace_text"
    )

    return dict(definition.input_schema)


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


def build_initial_request(
    *,
    task_text: str,
    workspace_root: Path,
    source_files: list[str],
) -> str:
    return "\n".join(
        [
            "Modify the repository to satisfy this task.",
            "",
            f"Task:\n{task_text}",
            "",
            (
                "You may make multiple sequential "
                "replace_text edits."
            ),
            (
                "Make one edit at a time. After each "
                "attempt you will receive the application "
                "result and updated source."
            ),
            (
                "When no more edits are required, return "
                'exactly {"type":"done"}.'
            ),
            "",
            "Current relevant source:",
            current_sources(
                workspace_root=workspace_root,
                source_files=source_files,
            ),
        ]
    )


def build_system_prompt(
    registry: ToolRegistry,
) -> str:
    schema = json.dumps(
        replace_schema(registry),
        sort_keys=True,
    )

    return (
        "You are the editing-action model inside Hewn.\n"
        "Your job is to modify repository code using "
        "sequential exact replacements.\n\n"
        "At each turn choose exactly one action.\n\n"
        "To edit, respond exactly as:\n"
        '{"type":"tool_call","name":"replace_text",'
        '"arguments":{"path":"FILE","old":"OLD_TEXT",'
        '"new":"NEW_TEXT"}}\n\n'
        "When all required edits have been proposed, "
        "respond exactly as:\n"
        '{"type":"done"}\n\n'
        "replace_text arguments must satisfy:\n"
        f"{schema}\n\n"
        "The old text must exist exactly in the current "
        "repository and occur exactly once.\n"
        "Use the application observation and updated "
        "source after each attempt when choosing the "
        "next action.\n"
        "Do not use Markdown fences. Do not explain. "
        "Return exactly one JSON object."
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


def parse_sequential_action(
    raw_response: str,
) -> SequentialAction:
    try:
        payload: Any = json.loads(raw_response)
    except json.JSONDecodeError:
        return SequentialAction(
            raw_response=raw_response,
            kind="protocol_failure",
            call=None,
            protocol_error=(
                "Model response is not valid JSON"
            ),
        )

    if not isinstance(payload, dict):
        return SequentialAction(
            raw_response=raw_response,
            kind="protocol_failure",
            call=None,
            protocol_error=(
                "Model response must be a JSON object"
            ),
        )

    if payload == {"type": "done"}:
        return SequentialAction(
            raw_response=raw_response,
            kind="done",
            call=None,
            protocol_error=None,
        )

    try:
        if set(payload) != {
            "type",
            "name",
            "arguments",
        }:
            raise ModelProtocolError(
                "Tool call has unexpected fields",
                raw_response=raw_response,
            )

        if payload["type"] != "tool_call":
            raise ModelProtocolError(
                "Expected tool_call or done",
                raw_response=raw_response,
            )

        if payload["name"] != "replace_text":
            raise ModelProtocolError(
                "Only replace_text is permitted",
                raw_response=raw_response,
            )

        arguments = payload["arguments"]

        if not isinstance(arguments, dict):
            raise ModelProtocolError(
                "Tool arguments must be an object",
                raw_response=raw_response,
            )

        call = ToolCall(
            name="replace_text",
            arguments=arguments,
        )

    except ModelProtocolError as exc:
        return SequentialAction(
            raw_response=exc.raw_response,
            kind="protocol_failure",
            call=None,
            protocol_error=(
                f"{type(exc).__name__}: {exc}"
            ),
        )

    return SequentialAction(
        raw_response=raw_response,
        kind="tool_call",
        call=call,
        protocol_error=None,
    )


def build_observation_message(
    *,
    application_succeeded: bool,
    application_output: str | None,
    application_error: str | None,
    workspace_root: Path,
    source_files: list[str],
    attempts_used: int,
) -> str:
    if application_succeeded:
        result = "The replace_text operation succeeded."
    else:
        result = (
            "The replace_text operation failed.\n"
            f"Error: {application_error}"
        )

    if application_output:
        result += (
            "\nTool output: "
            f"{application_output}"
        )

    remaining = MAX_EDIT_ATTEMPTS - attempts_used

    return "\n".join(
        [
            result,
            "",
            f"Edit attempts remaining: {remaining}",
            "",
            "Current relevant source:",
            current_sources(
                workspace_root=workspace_root,
                source_files=source_files,
            ),
            (
                'Return another replace_text action, or '
                '{"type":"done"} if the task is complete.'
            ),
        ]
    )


def classify_outcome(
    *,
    protocol_failure: bool,
    model_failure: bool,
    edit_attempts: int,
    successful_edits: int,
    syntax_valid: bool,
    verification_passed: bool,
    tests_changed: bool,
    unexpected_files_changed: list[str],
    exhausted: bool,
) -> str:
    if model_failure:
        return "model_failure"

    if protocol_failure:
        return "protocol_failure"

    if edit_attempts == 0:
        return "no_edit"

    if successful_edits == 0:
        return "application_failure"

    if not syntax_valid:
        return "invalid_code"

    if tests_changed:
        return "verification_failure"

    if verification_passed:
        if unexpected_files_changed:
            return "success_with_extra_changes"

        return "success"

    if exhausted:
        return "attempt_limit"

    return "verification_failure"


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
        prefix=f"hewn-sequential-{task_id}-"
    ) as temporary_directory:
        workspace_root = (
            Path(temporary_directory) / task_id
        )

        shutil.copytree(
            fixture_root,
            workspace_root,
        )

        before = snapshot_files(workspace_root)

        workspace = Workspace(workspace_root)
        registry = make_replace_registry(workspace)
        executor = ToolExecutor(registry)

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": build_system_prompt(
                    registry
                ),
            },
            {
                "role": "user",
                "content": build_initial_request(
                    task_text=str(task["task"]),
                    workspace_root=workspace_root,
                    source_files=source_files,
                ),
            },
        ]

        turns: list[dict[str, Any]] = []

        edit_attempts = 0
        successful_edits = 0
        failed_edits = 0

        done = False
        exhausted = False
        protocol_failure = False
        protocol_error: str | None = None
        model_failure = False
        model_error: str | None = None

        started = perf_counter()

        while edit_attempts < MAX_EDIT_ATTEMPTS:
            try:
                raw_response = call_llama(
                    messages=messages
                )
            except RuntimeError as exc:
                model_failure = True
                model_error = (
                    f"{type(exc).__name__}: {exc}"
                )
                break

            action = parse_sequential_action(
                raw_response
            )

            turn_record: dict[str, Any] = {
                "raw_response": raw_response,
                "kind": action.kind,
                "protocol_error": (
                    action.protocol_error
                ),
                "parsed_arguments": (
                    action.call.arguments
                    if action.call is not None
                    else None
                ),
                "application_succeeded": None,
                "application_output": None,
                "application_error": None,
            }

            messages.append(
                {
                    "role": "assistant",
                    "content": raw_response,
                }
            )

            if action.kind == "protocol_failure":
                protocol_failure = True
                protocol_error = (
                    action.protocol_error
                )
                turns.append(turn_record)
                break

            if action.kind == "done":
                done = True
                turns.append(turn_record)
                break

            if action.call is None:
                protocol_failure = True
                protocol_error = (
                    "Parsed tool action contained no call"
                )
                turns.append(turn_record)
                break

            edit_attempts += 1

            result = executor.execute(
                action.call
            )

            turn_record[
                "application_succeeded"
            ] = result.ok
            turn_record[
                "application_output"
            ] = result.output
            turn_record[
                "application_error"
            ] = result.error

            if result.ok:
                successful_edits += 1
            else:
                failed_edits += 1

            turns.append(turn_record)

            messages.append(
                {
                    "role": "user",
                    "content": build_observation_message(
                        application_succeeded=(
                            result.ok
                        ),
                        application_output=(
                            result.output
                        ),
                        application_error=(
                            result.error
                        ),
                        workspace_root=(
                            workspace_root
                        ),
                        source_files=source_files,
                        attempts_used=edit_attempts,
                    ),
                }
            )

        if (
            not done
            and not protocol_failure
            and not model_failure
            and edit_attempts >= MAX_EDIT_ATTEMPTS
        ):
            exhausted = True

        model_and_application_seconds = (
            perf_counter() - started
        )

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

        independent_tests = (
            run_independent_tests(
                workspace_root
            )
        )

        allowed_files = set(source_files)

        unexpected_changed = [
            path
            for path in changed
            if path not in allowed_files
        ]

        tests_changed = (
            test_file in changed
        )

        behavior_correct = (
            bool(independent_tests["passed"])
            and not tests_changed
        )

        outcome = classify_outcome(
            protocol_failure=protocol_failure,
            model_failure=model_failure,
            edit_attempts=edit_attempts,
            successful_edits=successful_edits,
            syntax_valid=syntax_valid,
            verification_passed=bool(
                independent_tests["passed"]
            ),
            tests_changed=tests_changed,
            unexpected_files_changed=(
                unexpected_changed
            ),
            exhausted=exhausted,
        )

        return {
            "task_id": task_id,
            "category": task["category"],
            "task": task["task"],
            "source_files": source_files,
            "test_file": test_file,
            "outcome": outcome,
            "behavior_correct": behavior_correct,
            "done": done,
            "exhausted": exhausted,
            "protocol_failure": (
                protocol_failure
            ),
            "protocol_error": protocol_error,
            "model_failure": model_failure,
            "model_error": model_error,
            "edit_attempts": edit_attempts,
            "successful_edits": successful_edits,
            "failed_edits": failed_edits,
            "turns": turns,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "verification": independent_tests,
            "files_modified": changed,
            "unexpected_files_modified": (
                unexpected_changed
            ),
            "tests_modified": tests_changed,
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "diff": diff_text,
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
        "Editing primitive: replace_text"
    )
    print(
        f"Maximum edit attempts: {MAX_EDIT_ATTEMPTS}"
    )
    print(
        "Application feedback: enabled"
    )
    print(
        "Updated source after each attempt: enabled"
    )
    print(
        "Verification: evaluator-side only"
    )
    print(
        f"Tasks: {len(tasks)}"
    )
    print(
        "Runs per task: 1"
    )
    print()

    records: list[dict[str, Any]] = []

    started = perf_counter()

    for task in tasks:
        print(
            f"{task['id']}: {task['category']}"
        )

        record = run_task(task)
        records.append(record)

        print(
            "  "
            f"outcome={record['outcome']} "
            f"behavior="
            f"{'PASS' if record['behavior_correct'] else 'FAIL'} "
            f"attempts={record['edit_attempts']} "
            f"applied={record['successful_edits']} "
            f"rejected={record['failed_edits']} "
            f"done={record['done']} "
            f"files={len(record['files_modified'])} "
            f"lines=+{record['lines_added']}"
            f"/-{record['lines_deleted']} "
            f"time="
            f"{record['model_and_application_seconds']:.2f}s"
        )

        if record["protocol_error"] is not None:
            print(
                "  protocol_error="
                f"{record['protocol_error']}"
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
        not bool(record["protocol_failure"])
        for record in records
    )

    total_edit_attempts = sum(
        int(record["edit_attempts"])
        for record in records
    )

    total_successful_edits = sum(
        int(record["successful_edits"])
        for record in records
    )

    total_failed_edits = sum(
        int(record["failed_edits"])
        for record in records
    )

    completed_by_model = sum(
        bool(record["done"])
        for record in records
    )

    exhausted_tasks = sum(
        bool(record["exhausted"])
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
            "module_6_sequential_replace_text"
        ),
        "configuration": {
            "coding_model": CODING_MODEL,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "editing_primitive": (
                "replace_text"
            ),
            "max_edit_attempts": (
                MAX_EDIT_ATTEMPTS
            ),
            "application_feedback": True,
            "updated_source_after_attempt": True,
            "source_supplied": True,
            "verification": (
                "evaluator_side_only"
            ),
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
            "completed_by_model": (
                completed_by_model
            ),
            "exhausted_tasks": (
                exhausted_tasks
            ),
            "total_edit_attempts": (
                total_edit_attempts
            ),
            "total_successful_edits": (
                total_successful_edits
            ),
            "total_failed_edits": (
                total_failed_edits
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
        "Model returned done: "
        f"{completed_by_model}/{len(tasks)}"
    )
    print(
        "Attempt-limit exhaustion: "
        f"{exhausted_tasks}/{len(tasks)}"
    )
    print(
        "Total edit attempts: "
        f"{total_edit_attempts}"
    )
    print(
        "Successful edit applications: "
        f"{total_successful_edits}"
    )
    print(
        "Rejected edit applications: "
        f"{total_failed_edits}"
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
    raise SystemExit(main())