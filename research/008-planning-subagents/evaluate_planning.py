from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from grounding import extract_structure, format_structure
from planning import Plan, PlanningProtocolError, parse_plan
from prompt import SYSTEM_PROMPT, build_prompt

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = ROOT / "research" / "008-planning-subagents"
MANIFEST = RESEARCH_DIR / "fixtures" / "manifest.json"
RESULTS_DIR = RESEARCH_DIR / "results"


@dataclass(frozen=True)
class Score:
    protocol_valid: bool
    required_file_recall: float | None
    required_file_precision: float | None
    unnecessary_files: int | None
    required_symbol_recall: float | None
    verification_recall: float | None
    verification_precision: float | None


@dataclass(frozen=True)
class RunRecord:
    task_id: str
    category: str
    condition: str
    prompt_chars: int
    response_chars: int
    latency_seconds: float
    raw_response: str
    protocol_error: str | None
    planned_files: list[str] | None
    planned_symbols: list[str] | None
    planned_verification: list[str] | None
    score: Score


def load_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text())

    if not isinstance(value, dict):
        raise TypeError("manifest must be an object")

    return value


def require_string_list(
    value: Any,
    *,
    field: str,
) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{field} must be a list")

    if not all(
        isinstance(item, str) and item
        for item in value
    ):
        raise TypeError(
            f"{field} must contain non-empty strings"
        )

    return value


def require_files(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError("files must be an object")

    result: dict[str, str] = {}

    for path, source in value.items():
        if not isinstance(path, str):
            raise TypeError(
                "file paths must be strings"
            )

        if not isinstance(source, str):
            raise TypeError(
                "file sources must be strings"
            )

        result[path] = source

    return result


def recall(
    expected: set[str],
    actual: set[str],
) -> float:
    if not expected:
        return 1.0

    return len(expected & actual) / len(expected)


def precision(
    expected: set[str],
    actual: set[str],
) -> float:
    if not actual:
        return 0.0

    return len(expected & actual) / len(actual)


def plan_symbols(plan: Plan) -> set[str]:
    return {
        symbol
        for planned_file in plan.files
        for symbol in planned_file.symbols
    }


def score_plan(
    plan: Plan,
    *,
    required_files: list[str],
    required_symbols: list[str],
    required_verification: list[str],
) -> Score:
    expected_files = set(required_files)
    actual_files = {
        planned_file.path
        for planned_file in plan.files
    }

    expected_symbols = set(required_symbols)
    actual_symbols = plan_symbols(plan)

    expected_verification = set(
        required_verification
    )
    actual_verification = set(
        plan.verification
    )

    return Score(
        protocol_valid=True,
        required_file_recall=recall(
            expected_files,
            actual_files,
        ),
        required_file_precision=precision(
            expected_files,
            actual_files,
        ),
        unnecessary_files=len(
            actual_files - expected_files
        ),
        required_symbol_recall=recall(
            expected_symbols,
            actual_symbols,
        ),
        verification_recall=recall(
            expected_verification,
            actual_verification,
        ),
        verification_precision=precision(
            expected_verification,
            actual_verification,
        ),
    )


def invalid_score() -> Score:
    return Score(
        protocol_valid=False,
        required_file_recall=None,
        required_file_precision=None,
        unnecessary_files=None,
        required_symbol_recall=None,
        verification_recall=None,
        verification_precision=None,
    )


def extract_content(body: str) -> str:
    try:
        payload: Any = json.loads(body)
        content = payload[
            "choices"
        ][0]["message"]["content"]
    except (
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise RuntimeError(
            "llama.cpp returned an invalid "
            "chat response"
        ) from exc

    if not isinstance(content, str):
        raise RuntimeError(
            "llama.cpp returned non-text "
            "assistant content"
        )

    return content


def call_planner(
    *,
    base_url: str,
    prompt: str,
) -> tuple[str, float]:
    payload = {
        "model": "local",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.0,
        "max_tokens": 512,
    }

    request = Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started = time.perf_counter()

    try:
        with urlopen(
            request,
            timeout=120.0,
        ) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(
            "llama.cpp returned HTTP "
            f"{exc.code}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            "Could not reach llama.cpp: "
            f"{exc.reason}"
        ) from exc

    elapsed = time.perf_counter() - started

    return extract_content(body), elapsed


def run_condition(
    *,
    base_url: str,
    task: dict[str, Any],
    condition: str,
) -> RunRecord:
    task_id = task.get("task_id")
    category = task.get("category")
    task_text = task.get("task")

    if not isinstance(task_id, str):
        raise TypeError(
            "task_id must be a string"
        )

    if not isinstance(category, str):
        raise TypeError(
            f"{task_id}: category must "
            "be a string"
        )

    if not isinstance(task_text, str):
        raise TypeError(
            f"{task_id}: task must "
            "be a string"
        )

    files = require_files(
        task.get("files")
    )

    required_files = require_string_list(
        task.get("required_files"),
        field=f"{task_id}.required_files",
    )
    required_symbols = require_string_list(
        task.get("required_symbols"),
        field=f"{task_id}.required_symbols",
    )
    required_verification = require_string_list(
        task.get("required_verification"),
        field=(
            f"{task_id}."
            "required_verification"
        ),
    )

    if condition == "source_only":
        structure = None
    elif condition == "source_plus_structure":
        structure = format_structure(
            extract_structure(files)
        )
    else:
        raise ValueError(
            f"unknown condition: {condition}"
        )

    prompt = build_prompt(
        task=task_text,
        files=files,
        structure=structure,
    )

    raw_response, latency = call_planner(
        base_url=base_url,
        prompt=prompt,
    )

    try:
        plan = parse_plan(raw_response)
    except PlanningProtocolError as exc:
        return RunRecord(
            task_id=task_id,
            category=category,
            condition=condition,
            prompt_chars=len(
                SYSTEM_PROMPT + prompt
            ),
            response_chars=len(
                raw_response
            ),
            latency_seconds=latency,
            raw_response=raw_response,
            protocol_error=str(exc),
            planned_files=None,
            planned_symbols=None,
            planned_verification=None,
            score=invalid_score(),
        )

    score = score_plan(
        plan,
        required_files=required_files,
        required_symbols=required_symbols,
        required_verification=(
            required_verification
        ),
    )

    return RunRecord(
        task_id=task_id,
        category=category,
        condition=condition,
        prompt_chars=len(
            SYSTEM_PROMPT + prompt
        ),
        response_chars=len(
            raw_response
        ),
        latency_seconds=latency,
        raw_response=raw_response,
        protocol_error=None,
        planned_files=[
            planned_file.path
            for planned_file in plan.files
        ],
        planned_symbols=sorted(
            plan_symbols(plan)
        ),
        planned_verification=list(
            plan.verification
        ),
        score=score,
    )


def write_record(
    run_dir: Path,
    record: RunRecord,
) -> None:
    condition_dir = (
        run_dir
        / record.condition
        / record.task_id
    )
    condition_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        condition_dir
        / "raw_response.txt"
    ).write_text(
        record.raw_response
    )

    (
        condition_dir
        / "record.json"
    ).write_text(
        json.dumps(
            asdict(record),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def mean_present(
    values: list[float | None],
) -> float | None:
    present = [
        value
        for value in values
        if value is not None
    ]

    if not present:
        return None

    return sum(present) / len(present)


def summarize(
    records: list[RunRecord],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}

    for condition in (
        "source_only",
        "source_plus_structure",
    ):
        selected = [
            record
            for record in records
            if record.condition == condition
        ]

        valid = [
            record
            for record in selected
            if record.score.protocol_valid
        ]

        summary[condition] = {
            "tasks": len(selected),
            "protocol_valid": len(valid),
            "protocol_rate": (
                len(valid) / len(selected)
                if selected
                else None
            ),
            "mean_required_file_recall_valid_only":
                mean_present(
                    [
                        record.score.required_file_recall
                        for record in selected
                    ]
                ),
            "mean_required_file_precision_valid_only":
                mean_present(
                    [
                        record.score.required_file_precision
                        for record in selected
                    ]
                ),
            "mean_required_symbol_recall_valid_only":
                mean_present(
                    [
                        record.score.required_symbol_recall
                        for record in selected
                    ]
                ),
            "mean_verification_recall_valid_only":
                mean_present(
                    [
                        record.score.verification_recall
                        for record in selected
                    ]
                ),
            "mean_verification_precision_valid_only":
                mean_present(
                    [
                        record.score.verification_precision
                        for record in selected
                    ]
                ),
            "total_unnecessary_files_valid_only":
                sum(
                    record.score.unnecessary_files
                    or 0
                    for record in valid
                ),
            "mean_prompt_chars":
                (
                    sum(
                        record.prompt_chars
                        for record in selected
                    )
                    / len(selected)
                ),
            "mean_response_chars":
                (
                    sum(
                        record.response_chars
                        for record in selected
                    )
                    / len(selected)
                ),
            "total_latency_seconds":
                sum(
                    record.latency_seconds
                    for record in selected
                ),
        }

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-id",
        required=True,
        help=(
            "Immutable result directory name, "
            "e.g. run-001"
        ),
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_dir = RESULTS_DIR / args.run_id

    if run_dir.exists():
        raise FileExistsError(
            "Refusing to overwrite existing run: "
            f"{run_dir}"
        )

    run_dir.mkdir(parents=True)

    manifest = load_manifest()
    raw_tasks = manifest.get("tasks")

    if not isinstance(raw_tasks, list):
        raise TypeError(
            "tasks must be a list"
        )

    records: list[RunRecord] = []

    for raw_task in raw_tasks:
        if not isinstance(raw_task, dict):
            raise TypeError(
                "each task must be an object"
            )

        for condition in (
            "source_only",
            "source_plus_structure",
        ):
            task_id = raw_task.get(
                "task_id"
            )

            print(
                f"{task_id}: {condition}",
                flush=True,
            )

            record = run_condition(
                base_url=args.base_url,
                task=raw_task,
                condition=condition,
            )

            # Save each response immediately.
            write_record(
                run_dir,
                record,
            )
            records.append(record)

            print(
                "  protocol="
                f"{record.score.protocol_valid} "
                "file_recall="
                f"{record.score.required_file_recall} "
                "verification_recall="
                f"{record.score.verification_recall} "
                "latency="
                f"{record.latency_seconds:.2f}s",
                flush=True,
            )

    summary = summarize(records)

    (
        run_dir
        / "summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print()
    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()