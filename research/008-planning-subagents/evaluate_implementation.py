from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from hewn.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "research" / "008-planning-subagents"

MANIFEST_PATH = MODULE_ROOT / "fixtures" / "manifest.json"
ORACLES_PATH = MODULE_ROOT / "fixtures" / "oracles.json"
PLANNING_RESULTS_ROOT = MODULE_ROOT / "results" / "run-002"
RESULTS_ROOT = MODULE_ROOT / "results"

BASE_URL = "http://127.0.0.1:8080"
CODING_MODEL = "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"
TEMPERATURE = 0.0
MAX_TOKENS = 512
TIMEOUT_SECONDS = 120.0
MAX_BATCH_EDITS = 6

CONDITIONS = (
    "direct",
    "plan_conditioned",
)

PROTECTED_PREFIX = "__hewn_oracle__/"


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


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


def load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def load_tasks() -> list[dict[str, Any]]:
    payload = load_json(MANIFEST_PATH)

    if not isinstance(payload, dict):
        raise TypeError("manifest must be an object")

    tasks = payload.get("tasks")

    if not isinstance(tasks, list):
        raise TypeError("manifest tasks must be a list")

    result: list[dict[str, Any]] = []

    for task in tasks:
        if not isinstance(task, dict):
            raise TypeError("each task must be an object")

        result.append(task)

    return result


def load_oracles() -> dict[str, str]:
    payload = load_json(ORACLES_PATH)

    if not isinstance(payload, dict):
        raise TypeError("oracles must be an object")

    result: dict[str, str] = {}

    for key, value in payload.items():
        if not isinstance(key, str):
            raise TypeError("oracle task IDs must be strings")

        if not isinstance(value, str):
            raise TypeError("oracle sources must be strings")

        result[key] = value

    return result


def require_string_list(
    value: Any,
    *,
    name: str,
) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")

    result: list[str] = []

    for item in value:
        if not isinstance(item, str):
            raise TypeError(
                f"{name} entries must be strings"
            )

        result.append(item)

    return result


def require_string_map(
    value: Any,
    *,
    name: str,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")

    result: dict[str, str] = {}

    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(
                f"{name} keys must be strings"
            )

        if not isinstance(item, str):
            raise TypeError(
                f"{name} values must be strings"
            )

        result[key] = item

    return result


def materialize_repository(
    *,
    root: Path,
    files: dict[str, str],
    oracle: str,
) -> None:
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            source,
            encoding="utf-8",
        )

    oracle_path = (
        root
        / "__hewn_oracle__"
        / "test_behavior.py"
    )
    oracle_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    oracle_path.write_text(
        oracle,
        encoding="utf-8",
    )


def snapshot_visible_files(
    root: Path,
) -> dict[str, str]:
    snapshot: dict[str, str] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if relative.parts[0] == "__hewn_oracle__":
            continue

        if "__pycache__" in relative.parts:
            continue

        if ".pytest_cache" in relative.parts:
            continue

        if path.suffix == ".pyc":
            continue

        try:
            source = path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            continue

        snapshot[relative.as_posix()] = source

    return snapshot


def format_visible_repository(
    root: Path,
) -> str:
    snapshot = snapshot_visible_files(root)
    sections: list[str] = []

    for number, path in enumerate(
        sorted(snapshot),
        start=1,
    ):
        sections.extend(
            [
                f"[File {number}]",
                f"path: {path}",
                snapshot[path],
                "",
            ]
        )

    return "\n".join(sections)


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
        sections.extend(
            difflib.unified_diff(
                before.get(
                    path,
                    "",
                ).splitlines(keepends=True),
                after.get(
                    path,
                    "",
                ).splitlines(keepends=True),
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


def build_system_prompt() -> str:
    return f"""You are the editing-action model inside Hewn.

Your only job is to propose a complete batch of exact text replacements
needed to satisfy the task.

Your entire response must be exactly one valid JSON object.
The first character of your response must be {{.
The last character of your response must be }}.
Do not use ```json.
Do not use Markdown fences.
Do not write prose before or after the JSON.

Use exactly this shape:

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
- Return all edits needed to complete the task in this one response.
- Each edit uses exact text replacement.
- "old" must match repository text exactly.
- "old" must occur exactly once at the point that edit is applied.
- Edits are applied in array order.
- A later edit may target text produced by an earlier edit.
- For insertion, replace a unique existing anchor with the anchor plus
  the required inserted text.
- For changes in multiple locations, emit multiple edits.
- For changes in multiple files, emit edits for every required file.
- Visible tests may be modified when required by the task.
- Never target __hewn_oracle__.
- Do not emit a final answer.
- Do not include explanations.
"""


def build_user_prompt(
    *,
    task_text: str,
    repository_text: str,
    plan_text: str | None,
) -> str:
    sections = [
        (
            "Produce the complete edit batch required "
            "to satisfy this task."
        ),
        "",
        f"Task:\n{task_text}",
        "",
        "Visible repository:",
        repository_text,
    ]

    if plan_text is not None:
        sections.extend(
            [
                "",
                (
                    "Explicit plan produced by the planning "
                    "stage:"
                ),
                plan_text,
                "",
                (
                    "Use the plan as implementation guidance, "
                    "but the task and repository remain the "
                    "source of truth."
                ),
            ]
        )

    return "\n".join(sections)


def call_llama(
    *,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, float]:
    payload = {
        "model": "local",
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

    request = Request(
        f"{BASE_URL}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started = perf_counter()

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

    duration = perf_counter() - started

    try:
        response_payload: Any = json.loads(body)
        content = response_payload[
            "choices"
        ][0]["message"]["content"]
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
            "llama.cpp returned non-text content"
        )

    return content, duration


def protocol_failure(
    raw_response: str,
    message: str,
) -> BatchProposal:
    return BatchProposal(
        raw_response=raw_response,
        edits=(),
        protocol_error=message,
    )


def parse_batch_proposal(
    raw_response: str,
) -> BatchProposal:
    try:
        payload: Any = json.loads(raw_response)
    except json.JSONDecodeError:
        return protocol_failure(
            raw_response,
            "Model response is not valid JSON",
        )

    if not isinstance(payload, dict):
        return protocol_failure(
            raw_response,
            "Model response must be a JSON object",
        )

    if set(payload) != {"type", "edits"}:
        return protocol_failure(
            raw_response,
            "Batch response has unexpected fields",
        )

    if payload["type"] != "edit_batch":
        return protocol_failure(
            raw_response,
            "Response type must be edit_batch",
        )

    raw_edits = payload["edits"]

    if not isinstance(raw_edits, list):
        return protocol_failure(
            raw_response,
            "edits must be an array",
        )

    if not 1 <= len(raw_edits) <= MAX_BATCH_EDITS:
        return protocol_failure(
            raw_response,
            (
                "edit batch must contain between "
                f"1 and {MAX_BATCH_EDITS} edits"
            ),
        )

    parsed: list[BatchEdit] = []

    for index, raw_edit in enumerate(raw_edits):
        if not isinstance(raw_edit, dict):
            return protocol_failure(
                raw_response,
                f"edit {index} must be an object",
            )

        if set(raw_edit) != {
            "path",
            "old",
            "new",
        }:
            return protocol_failure(
                raw_response,
                (
                    f"edit {index} has unexpected "
                    "fields"
                ),
            )

        path = raw_edit["path"]
        old = raw_edit["old"]
        new = raw_edit["new"]

        if not isinstance(path, str):
            return protocol_failure(
                raw_response,
                f"edit {index} path must be a string",
            )

        if not isinstance(old, str):
            return protocol_failure(
                raw_response,
                f"edit {index} old must be a string",
            )

        if not isinstance(new, str):
            return protocol_failure(
                raw_response,
                f"edit {index} new must be a string",
            )

        if not path:
            return protocol_failure(
                raw_response,
                f"edit {index} path must not be empty",
            )

        if not old:
            return protocol_failure(
                raw_response,
                f"edit {index} old must not be empty",
            )

        if old == new:
            return protocol_failure(
                raw_response,
                f"edit {index} must not be a no-op",
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


def resolve_edit_path(
    *,
    workspace: Workspace,
    relative_path: str,
) -> Path:
    if relative_path.startswith(
        PROTECTED_PREFIX
    ):
        raise ValueError(
            "hidden oracle paths are protected"
        )

    return workspace.resolve(relative_path)


def preflight_batch(
    *,
    workspace: Workspace,
    proposal: BatchProposal,
) -> tuple[
    PreflightResult,
    dict[Path, str],
]:
    if proposal.protocol_error is not None:
        return (
            PreflightResult(
                valid=False,
                failed_edit_index=None,
                error=proposal.protocol_error,
            ),
            {},
        )

    simulated: dict[Path, str] = {}

    for index, edit in enumerate(proposal.edits):
        try:
            path = resolve_edit_path(
                workspace=workspace,
                relative_path=edit.path,
            )
        except (ValueError, OSError) as exc:
            return (
                PreflightResult(
                    valid=False,
                    failed_edit_index=index,
                    error=str(exc),
                ),
                {},
            )

        if not path.exists():
            return (
                PreflightResult(
                    valid=False,
                    failed_edit_index=index,
                    error=(
                        f"path does not exist: "
                        f"{edit.path}"
                    ),
                ),
                {},
            )

        if not path.is_file():
            return (
                PreflightResult(
                    valid=False,
                    failed_edit_index=index,
                    error=(
                        f"path is not a file: "
                        f"{edit.path}"
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
                            f"path is not UTF-8: "
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
                    error=(
                        "old text was not found in "
                        f"{edit.path}"
                    ),
                ),
                {},
            )

        if occurrences > 1:
            return (
                PreflightResult(
                    valid=False,
                    failed_edit_index=index,
                    error=(
                        "old text occurs more than once "
                        f"in {edit.path}"
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


def parse_all_python(
    root: Path,
) -> tuple[bool, str | None]:
    for path in sorted(root.rglob("*.py")):
        if "__hewn_oracle__" in path.parts:
            continue

        try:
            source = path.read_text(
                encoding="utf-8"
            )
            ast.parse(
                source,
                filename=str(path),
            )
        except (
            UnicodeDecodeError,
            SyntaxError,
        ) as exc:
            return False, str(exc)

    return True, None


def run_hidden_oracle(
    root: Path,
) -> VerificationResult:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")

    started = perf_counter()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "__hewn_oracle__/test_behavior.py",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    duration = perf_counter() - started

    return VerificationResult(
        passed=result.returncode == 0,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=duration,
    )


def load_frozen_plan(task_id: str) -> str:
    path = (
        PLANNING_RESULTS_ROOT
        / "source_plus_structure"
        / task_id
        / "raw_response.txt"
    )

    raw = path.read_text(encoding="utf-8")

    payload: Any = json.loads(raw)

    if not isinstance(payload, dict):
        raise TypeError(
            f"{task_id}: frozen plan is not an object"
        )

    return json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )


def score_changed_files(
    *,
    required_files: list[str],
    actual_files: list[str],
) -> dict[str, float | int]:
    required = set(required_files)
    actual = set(actual_files)

    intersection = required & actual

    recall = (
        len(intersection) / len(required)
        if required
        else 1.0
    )

    precision = (
        len(intersection) / len(actual)
        if actual
        else 0.0
    )

    return {
        "required_file_recall": recall,
        "required_file_precision": precision,
        "unnecessary_changed_files": len(
            actual - required
        ),
    }


def write_text(
    path: Path,
    text: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        text,
        encoding="utf-8",
    )


def evaluate_task(
    *,
    task: dict[str, Any],
    oracle: str,
    condition: str,
    result_dir: Path,
) -> dict[str, Any]:
    task_id = task.get("task_id")
    task_text = task.get("task")

    if not isinstance(task_id, str):
        raise TypeError("task_id must be a string")

    if not isinstance(task_text, str):
        raise TypeError(
            f"{task_id}: task must be a string"
        )

    files = require_string_map(
        task.get("files"),
        name=f"{task_id}.files",
    )
    required_files = require_string_list(
        task.get("required_files"),
        name=f"{task_id}.required_files",
    )

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        materialize_repository(
            root=root,
            files=files,
            oracle=oracle,
        )

        before = snapshot_visible_files(root)

        repository_text = (
            format_visible_repository(root)
        )

        plan_text = (
            load_frozen_plan(task_id)
            if condition == "plan_conditioned"
            else None
        )

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(
            task_text=task_text,
            repository_text=repository_text,
            plan_text=plan_text,
        )

        raw_response, model_seconds = call_llama(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        write_text(
            result_dir / "raw_response.txt",
            raw_response,
        )
        write_text(
            result_dir / "user_prompt.txt",
            user_prompt,
        )

        if plan_text is not None:
            write_text(
                result_dir / "plan.json",
                plan_text,
            )

        proposal = parse_batch_proposal(
            raw_response
        )

        workspace = Workspace(root)

        preflight, simulated = preflight_batch(
            workspace=workspace,
            proposal=proposal,
        )

        committed = False

        if preflight.valid:
            commit_simulated(simulated)
            committed = True

        syntax_valid = False
        syntax_error: str | None = None

        if committed:
            (
                syntax_valid,
                syntax_error,
            ) = parse_all_python(root)

        verification: VerificationResult | None = None

        if committed and syntax_valid:
            verification = run_hidden_oracle(root)

        after = snapshot_visible_files(root)

        actual_changed_files = changed_files(
            before,
            after,
        )

        diff_text = build_diff(
            before,
            after,
        )

        write_text(
            result_dir / "diff.patch",
            diff_text,
        )

        additions, deletions = diff_line_counts(
            diff_text
        )

        file_score = score_changed_files(
            required_files=required_files,
            actual_files=actual_changed_files,
        )

        behavioral_success = bool(
            verification is not None
            and verification.passed
        )

        if proposal.protocol_error is not None:
            outcome = "protocol_failure"
        elif not preflight.valid:
            outcome = "application_failure"
        elif not syntax_valid:
            outcome = "invalid_code"
        elif behavioral_success:
            outcome = "success"
        else:
            outcome = "verification_failure"

        record: dict[str, Any] = {
            "task_id": task_id,
            "category": task.get("category"),
            "condition": condition,
            "model": CODING_MODEL,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "prompt_chars": (
                len(system_prompt)
                + len(user_prompt)
            ),
            "response_chars": len(raw_response),
            "model_seconds": model_seconds,
            "protocol_valid": (
                proposal.protocol_error is None
            ),
            "protocol_error": (
                proposal.protocol_error
            ),
            "edit_count": len(proposal.edits),
            "preflight": asdict(preflight),
            "committed": committed,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "changed_files": actual_changed_files,
            **file_score,
            "diff_additions": additions,
            "diff_deletions": deletions,
            "behavioral_success": behavioral_success,
            "outcome": outcome,
            "verification": (
                asdict(verification)
                if verification is not None
                else None
            ),
        }

        write_text(
            result_dir / "record.json",
            json.dumps(
                record,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

        return record


def mean(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def summarize(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}

    for condition in CONDITIONS:
        selected = [
            record
            for record in records
            if record["condition"] == condition
        ]

        summary[condition] = {
            "tasks": len(selected),
            "behavioral_successes": sum(
                bool(record["behavioral_success"])
                for record in selected
            ),
            "protocol_valid": sum(
                bool(record["protocol_valid"])
                for record in selected
            ),
            "preflight_valid": sum(
                bool(record["preflight"]["valid"])
                for record in selected
            ),
            "committed": sum(
                bool(record["committed"])
                for record in selected
            ),
            "syntax_valid": sum(
                bool(record["syntax_valid"])
                for record in selected
            ),
            "mean_required_file_recall": mean(
                [
                    float(
                        record[
                            "required_file_recall"
                        ]
                    )
                    for record in selected
                ]
            ),
            "mean_required_file_precision": mean(
                [
                    float(
                        record[
                            "required_file_precision"
                        ]
                    )
                    for record in selected
                ]
            ),
            "unnecessary_changed_files": sum(
                int(
                    record[
                        "unnecessary_changed_files"
                    ]
                )
                for record in selected
            ),
            "total_diff_additions": sum(
                int(record["diff_additions"])
                for record in selected
            ),
            "total_diff_deletions": sum(
                int(record["diff_deletions"])
                for record in selected
            ),
            "mean_prompt_chars": mean(
                [
                    float(record["prompt_chars"])
                    for record in selected
                ]
            ),
            "mean_response_chars": mean(
                [
                    float(record["response_chars"])
                    for record in selected
                ]
            ),
            "total_model_seconds": sum(
                float(record["model_seconds"])
                for record in selected
            ),
            "outcomes": {
                outcome: sum(
                    record["outcome"] == outcome
                    for record in selected
                )
                for outcome in (
                    "success",
                    "protocol_failure",
                    "application_failure",
                    "invalid_code",
                    "verification_failure",
                )
            },
        }

    return summary


def print_results(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    for record in records:
        print(
            record["task_id"],
            record["condition"],
            f"protocol={record['protocol_valid']}",
            (
                "preflight="
                f"{record['preflight']['valid']}"
            ),
            f"committed={record['committed']}",
            f"syntax={record['syntax_valid']}",
            (
                "behavior="
                f"{record['behavioral_success']}"
            ),
            f"outcome={record['outcome']}",
            (
                "files="
                f"{record['required_file_recall']:.3f}"
            ),
            (
                "latency="
                f"{record['model_seconds']:.2f}s"
            ),
        )

    print()
    print("Summary")

    for condition in CONDITIONS:
        data = summary[condition]

        print()
        print(condition)
        print(
            "  behavioral:",
            f"{data['behavioral_successes']}"
            f"/{data['tasks']}",
        )
        print(
            "  protocol:",
            f"{data['protocol_valid']}"
            f"/{data['tasks']}",
        )
        print(
            "  preflight:",
            f"{data['preflight_valid']}"
            f"/{data['tasks']}",
        )
        print(
            "  committed:",
            f"{data['committed']}"
            f"/{data['tasks']}",
        )
        print(
            "  file recall:",
            (
                f"{data['mean_required_file_recall']:.4f}"
            ),
        )
        print(
            "  file precision:",
            (
                f"{data['mean_required_file_precision']:.4f}"
            ),
        )
        print(
            "  unnecessary files:",
            data["unnecessary_changed_files"],
        )
        print(
            "  mean prompt chars:",
            f"{data['mean_prompt_chars']:.1f}",
        )
        print(
            "  total model seconds:",
            f"{data['total_model_seconds']:.2f}",
        )
        print(
            "  outcomes:",
            data["outcomes"],
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-id",
        required=True,
    )
    args = parser.parse_args()

    run_dir = (
        RESULTS_ROOT
        / f"implementation-{args.run_id}"
    )

    if run_dir.exists():
        raise FileExistsError(
            f"result directory already exists: {run_dir}"
        )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    tasks = load_tasks()
    oracles = load_oracles()

    records: list[dict[str, Any]] = []

    for task in tasks:
        task_id = task.get("task_id")

        if not isinstance(task_id, str):
            raise TypeError(
                "task_id must be a string"
            )

        oracle = oracles.get(task_id)

        if oracle is None:
            raise ValueError(
                f"missing oracle for {task_id}"
            )

        for condition in CONDITIONS:
            result_dir = (
                run_dir
                / condition
                / task_id
            )
            result_dir.mkdir(
                parents=True,
                exist_ok=False,
            )

            print(
                f"Running {task_id} "
                f"[{condition}]..."
            )

            record = evaluate_task(
                task=task,
                oracle=oracle,
                condition=condition,
                result_dir=result_dir,
            )

            records.append(record)

    summary = summarize(records)

    output = {
        "experiment": "008B",
        "run_id": args.run_id,
        "model": CODING_MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "planner": {
            "condition": (
                "source_plus_structure"
            ),
            "source_run": "008A run-002",
            "replayed": True,
        },
        "controls": {
            "implementer_calls_per_task": 1,
            "repair_calls": 0,
            "atomic_application": True,
            "hidden_oracle": True,
            "same_visible_repository": True,
        },
        "records": records,
        "summary": summary,
    }

    write_text(
        run_dir / "results.json",
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )

    print_results(
        records,
        summary,
    )


if __name__ == "__main__":
    main()