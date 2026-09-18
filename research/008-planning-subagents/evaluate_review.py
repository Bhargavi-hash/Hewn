from __future__ import annotations

import argparse
import importlib.util
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "research" / "008-planning-subagents"
MODULE7_ROOT = REPO_ROOT / "research" / "007-execution-feedback"

MANIFEST_PATH = MODULE_ROOT / "fixtures" / "manifest.json"
SOURCE_RUN_ROOT = MODULE_ROOT / "results" / "implementation-run-001"
RESULTS_ROOT = MODULE_ROOT / "results"

NORMALIZER_PATH = MODULE7_ROOT / "normalize_pytest.py"

BASE_URL = "http://127.0.0.1:8080"
MODEL = "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"
TEMPERATURE = 0.0
MAX_TOKENS = 256
TIMEOUT_SECONDS = 120.0

SOURCE_CONDITIONS = (
    "direct",
    "plan_conditioned",
)

REVIEW_CONDITIONS = (
    "patch_only",
    "execution_signal",
    "execution_evidence",
)

EXPECTED_COMMITTED = 14
EXPECTED_VERIFIED = 12
EXPECTED_RUNTIME_PASS = 2
EXPECTED_RUNTIME_FAIL = 10


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    task_id: str
    source_condition: str
    task_text: str
    repository_text: str
    diff_text: str
    syntax_valid: bool
    runtime_pass: bool | None
    verification_stdout: str | None
    verification_stderr: str | None


@dataclass(frozen=True)
class Review:
    verdict: str | None
    reason: str | None
    protocol_error: str | None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_normalizer() -> Callable[[str], dict[str, Any]]:
    spec = importlib.util.spec_from_file_location(
        "hewn_module7_normalize_pytest",
        NORMALIZER_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"could not load normalizer from {NORMALIZER_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    function = getattr(
        module,
        "normalize_pytest_output",
        None,
    )

    if not callable(function):
        raise TypeError(
            "Module 7 normalize_pytest_output is not callable"
        )

    def normalize(raw_output: str) -> dict[str, Any]:
        result = function(raw_output)

        if not isinstance(result, dict):
            raise TypeError(
                "normalize_pytest_output must return a dict"
            )

        return result

    return normalize


def load_tasks() -> dict[str, dict[str, Any]]:
    payload = load_json(MANIFEST_PATH)

    if not isinstance(payload, dict):
        raise TypeError("manifest must be an object")

    raw_tasks = payload.get("tasks")

    if not isinstance(raw_tasks, list):
        raise TypeError("manifest tasks must be a list")

    tasks: dict[str, dict[str, Any]] = {}

    for task in raw_tasks:
        if not isinstance(task, dict):
            raise TypeError("manifest task must be an object")

        task_id = task.get("task_id")

        if not isinstance(task_id, str):
            raise TypeError("task_id must be a string")

        if task_id in tasks:
            raise ValueError(f"duplicate task: {task_id}")

        tasks[task_id] = task

    return tasks


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
            raise TypeError(f"{name} keys must be strings")

        if not isinstance(item, str):
            raise TypeError(f"{name} values must be strings")

        result[key] = item

    return result


def format_original_repository(
    files: dict[str, str],
) -> str:
    sections: list[str] = []

    for number, path in enumerate(sorted(files), start=1):
        sections.extend(
            [
                f"[File {number}]",
                f"path: {path}",
                files[path],
                "",
            ]
        )

    return "\n".join(sections)


def optional_string(
    value: Any,
    *,
    name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or null")

    return value


def load_candidate(
    *,
    task: dict[str, Any],
    source_condition: str,
) -> Candidate | None:
    task_id = task.get("task_id")
    task_text = task.get("task")

    if not isinstance(task_id, str):
        raise TypeError("task_id must be a string")

    if not isinstance(task_text, str):
        raise TypeError(f"{task_id}: task must be a string")

    files = require_string_map(
        task.get("files"),
        name=f"{task_id}.files",
    )

    candidate_root = SOURCE_RUN_ROOT / source_condition / task_id
    record_path = candidate_root / "record.json"
    diff_path = candidate_root / "diff.patch"

    if not record_path.is_file():
        raise FileNotFoundError(record_path)

    if not diff_path.is_file():
        raise FileNotFoundError(diff_path)

    record = load_json(record_path)

    if not isinstance(record, dict):
        raise TypeError(
            f"{record_path} must contain an object"
        )

    committed = record.get("committed")

    if not isinstance(committed, bool):
        raise TypeError(
            f"{record_path}: committed must be bool"
        )

    if not committed:
        return None

    syntax_valid = record.get("syntax_valid")

    if not isinstance(syntax_valid, bool):
        raise TypeError(
            f"{record_path}: syntax_valid must be bool"
        )

    behavioral_success = record.get("behavioral_success")

    if not isinstance(behavioral_success, bool):
        raise TypeError(
            f"{record_path}: behavioral_success must be bool"
        )

    verification = record.get("verification")

    runtime_pass: bool | None
    verification_stdout: str | None
    verification_stderr: str | None

    if syntax_valid:
        if not isinstance(verification, dict):
            raise TypeError(
                f"{record_path}: syntax-valid committed "
                "candidate must contain verification"
            )

        stdout = verification.get("stdout")
        stderr = verification.get("stderr")

        if not isinstance(stdout, str):
            raise TypeError(
                f"{record_path}: verification stdout "
                "must be string"
            )

        if not isinstance(stderr, str):
            raise TypeError(
                f"{record_path}: verification stderr "
                "must be string"
            )

        runtime_pass = behavioral_success
        verification_stdout = stdout
        verification_stderr = stderr

    else:
        if verification is not None:
            raise ValueError(
                f"{record_path}: syntax-invalid candidate "
                "unexpectedly contains runtime verification"
            )

        if behavioral_success:
            raise ValueError(
                f"{record_path}: syntax-invalid candidate "
                "cannot have behavioral_success=true"
            )

        runtime_pass = None
        verification_stdout = None
        verification_stderr = None

    diff_text = diff_path.read_text(encoding="utf-8")

    if not diff_text.strip():
        raise ValueError(
            f"{task_id}/{source_condition}: "
            "committed candidate has empty diff"
        )

    return Candidate(
        candidate_id=f"{task_id}__{source_condition}",
        task_id=task_id,
        source_condition=source_condition,
        task_text=task_text,
        repository_text=format_original_repository(files),
        diff_text=diff_text,
        syntax_valid=syntax_valid,
        runtime_pass=runtime_pass,
        verification_stdout=verification_stdout,
        verification_stderr=verification_stderr,
    )


def load_corpus() -> list[Candidate]:
    tasks = load_tasks()
    candidates: list[Candidate] = []

    for task_id in sorted(tasks):
        task = tasks[task_id]

        for source_condition in SOURCE_CONDITIONS:
            candidate = load_candidate(
                task=task,
                source_condition=source_condition,
            )

            if candidate is not None:
                candidates.append(candidate)

    return candidates


def verified_candidates(
    candidates: list[Candidate],
) -> list[Candidate]:
    return [
        candidate
        for candidate in candidates
        if candidate.runtime_pass is not None
    ]


def validate_corpus(
    candidates: list[Candidate],
) -> None:
    if len(candidates) != EXPECTED_COMMITTED:
        raise AssertionError(
            f"expected {EXPECTED_COMMITTED} committed "
            f"candidates, found {len(candidates)}"
        )

    verified = verified_candidates(candidates)

    if len(verified) != EXPECTED_VERIFIED:
        raise AssertionError(
            f"expected {EXPECTED_VERIFIED} runtime-verified "
            f"candidates, found {len(verified)}"
        )

    passed = sum(
        candidate.runtime_pass is True
        for candidate in verified
    )
    failed = sum(
        candidate.runtime_pass is False
        for candidate in verified
    )

    if passed != EXPECTED_RUNTIME_PASS:
        raise AssertionError(
            f"expected {EXPECTED_RUNTIME_PASS} runtime-pass "
            f"candidates, found {passed}"
        )

    if failed != EXPECTED_RUNTIME_FAIL:
        raise AssertionError(
            f"expected {EXPECTED_RUNTIME_FAIL} runtime-fail "
            f"candidates, found {failed}"
        )

    unverified = [
        candidate
        for candidate in candidates
        if candidate.runtime_pass is None
    ]

    if len(unverified) != (
        EXPECTED_COMMITTED - EXPECTED_VERIFIED
    ):
        raise AssertionError(
            "unexpected number of unverified candidates"
        )

    if any(
        candidate.syntax_valid
        for candidate in unverified
    ):
        raise AssertionError(
            "runtime-unverified candidate was syntax valid"
        )

    candidate_ids = [
        candidate.candidate_id
        for candidate in candidates
    ]

    if len(candidate_ids) != len(set(candidate_ids)):
        raise AssertionError("candidate IDs are not unique")


def candidates_for_condition(
    candidates: list[Candidate],
    review_condition: str,
) -> list[Candidate]:
    if review_condition == "patch_only":
        return candidates

    if review_condition in {
        "execution_signal",
        "execution_evidence",
    }:
        return verified_candidates(candidates)

    raise ValueError(
        f"unknown review condition: {review_condition}"
    )


def combined_execution_output(
    candidate: Candidate,
) -> str:
    stdout = optional_string(
        candidate.verification_stdout,
        name="verification_stdout",
    )
    stderr = optional_string(
        candidate.verification_stderr,
        name="verification_stderr",
    )

    if stdout is None or stderr is None:
        raise ValueError(
            f"{candidate.candidate_id}: "
            "candidate has no runtime verification"
        )

    return "\n".join(
        part
        for part in (
            stdout.strip(),
            stderr.strip(),
        )
        if part
    )


def normalized_execution_evidence(
    *,
    candidate: Candidate,
    normalize: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    if candidate.runtime_pass is None:
        raise ValueError(
            f"{candidate.candidate_id}: "
            "candidate was not runtime verified"
        )

    if candidate.runtime_pass:
        return {
            "verification": "passed",
            "tool": "pytest",
        }

    raw_output = combined_execution_output(candidate)

    if not raw_output:
        raise ValueError(
            f"{candidate.candidate_id}: "
            "runtime failure has no execution output"
        )

    return normalize(raw_output)


def build_system_prompt() -> str:
    return """You are an independent code-review stage inside Hewn.

Judge whether the candidate patch satisfies the requested runtime behavior
without introducing a behavior that contradicts the task.

Your entire response must be exactly one valid JSON object.
The first character must be {.
The last character must be }.
Do not use Markdown fences.
Do not write prose before or after the JSON.

Use exactly this shape:

{
  "verdict": "accept",
  "reason": "short concrete reason"
}

or:

{
  "verdict": "reject",
  "reason": "short concrete reason"
}

Rules:

- verdict must be exactly "accept" or "reject".
- reason must be a non-empty string.
- Judge the candidate patch, not the intentions behind it.
- Do not propose edits.
- Do not output code.
- Do not invent test results.
- If execution evidence is provided, treat it as factual evidence.
- If execution evidence is not provided, reason only from the task,
  original repository, and patch.
"""


def build_user_prompt(
    *,
    candidate: Candidate,
    review_condition: str,
    normalize: Callable[[str], dict[str, Any]],
) -> str:
    sections = [
        "Review this candidate patch.",
        "",
        "Task:",
        candidate.task_text,
        "",
        "Original visible repository:",
        candidate.repository_text,
        "",
        "Candidate patch:",
        candidate.diff_text,
    ]

    if review_condition == "execution_signal":
        if candidate.runtime_pass is None:
            raise ValueError(
                "execution_signal requires runtime verification"
            )

        signal = (
            "PASS"
            if candidate.runtime_pass
            else "FAIL"
        )

        sections.extend(
            [
                "",
                "Deterministic runtime verification:",
                signal,
            ]
        )

    elif review_condition == "execution_evidence":
        evidence = normalized_execution_evidence(
            candidate=candidate,
            normalize=normalize,
        )

        sections.extend(
            [
                "",
                "Deterministic execution evidence:",
                json.dumps(
                    evidence,
                    indent=2,
                    sort_keys=True,
                ),
            ]
        )

    elif review_condition != "patch_only":
        raise ValueError(
            f"unknown condition: {review_condition}"
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
            f"could not reach llama.cpp: {exc.reason}"
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


def parse_review(raw_response: str) -> Review:
    try:
        payload: Any = json.loads(raw_response)
    except json.JSONDecodeError:
        return Review(
            verdict=None,
            reason=None,
            protocol_error="response is not valid JSON",
        )

    if not isinstance(payload, dict):
        return Review(
            verdict=None,
            reason=None,
            protocol_error="response must be an object",
        )

    if set(payload) != {"verdict", "reason"}:
        return Review(
            verdict=None,
            reason=None,
            protocol_error="response has unexpected fields",
        )

    verdict = payload["verdict"]
    reason = payload["reason"]

    if verdict not in {"accept", "reject"}:
        return Review(
            verdict=None,
            reason=None,
            protocol_error=(
                "verdict must be accept or reject"
            ),
        )

    if not isinstance(reason, str):
        return Review(
            verdict=None,
            reason=None,
            protocol_error="reason must be a string",
        )

    if not reason.strip():
        return Review(
            verdict=None,
            reason=None,
            protocol_error="reason must not be empty",
        )

    return Review(
        verdict=verdict,
        reason=reason,
        protocol_error=None,
    )


def classify(
    *,
    runtime_pass: bool | None,
    verdict: str | None,
) -> str | None:
    if runtime_pass is None:
        return None

    if verdict is None:
        return "protocol_failure"

    if runtime_pass:
        if verdict == "accept":
            return "true_positive"

        return "false_negative"

    if verdict == "reject":
        return "true_negative"

    return "false_positive"


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


def evaluate_candidate(
    *,
    candidate: Candidate,
    review_condition: str,
    normalize: Callable[[str], dict[str, Any]],
    result_dir: Path,
) -> dict[str, Any]:
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        candidate=candidate,
        review_condition=review_condition,
        normalize=normalize,
    )

    raw_response, model_seconds = call_llama(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    write_text(
        result_dir / "user_prompt.txt",
        user_prompt,
    )
    write_text(
        result_dir / "raw_response.txt",
        raw_response,
    )

    review = parse_review(raw_response)

    classification = classify(
        runtime_pass=candidate.runtime_pass,
        verdict=review.verdict,
    )

    record: dict[str, Any] = {
        "candidate_id": candidate.candidate_id,
        "task_id": candidate.task_id,
        "source_condition": candidate.source_condition,
        "review_condition": review_condition,
        "syntax_valid": candidate.syntax_valid,
        "runtime_pass": candidate.runtime_pass,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "prompt_chars": (
            len(system_prompt)
            + len(user_prompt)
        ),
        "response_chars": len(raw_response),
        "model_seconds": model_seconds,
        "protocol_valid": (
            review.protocol_error is None
        ),
        "protocol_error": review.protocol_error,
        "verdict": review.verdict,
        "reason": review.reason,
        "classification": classification,
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


def safe_rate(
    numerator: int,
    denominator: int,
) -> float | None:
    if denominator == 0:
        return None

    return numerator / denominator


def mean(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def summarize_verified(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    verified = [
        record
        for record in records
        if record["runtime_pass"] is not None
    ]

    tp = sum(
        record["classification"] == "true_positive"
        for record in verified
    )
    tn = sum(
        record["classification"] == "true_negative"
        for record in verified
    )
    fp = sum(
        record["classification"] == "false_positive"
        for record in verified
    )
    fn = sum(
        record["classification"] == "false_negative"
        for record in verified
    )
    protocol_failures = sum(
        record["classification"] == "protocol_failure"
        for record in verified
    )

    runtime_pass_total = sum(
        record["runtime_pass"] is True
        for record in verified
    )
    runtime_fail_total = sum(
        record["runtime_pass"] is False
        for record in verified
    )

    pass_recall = safe_rate(tp, runtime_pass_total)
    fail_recall = safe_rate(tn, runtime_fail_total)

    balanced_accuracy: float | None

    if (
        pass_recall is None
        or fail_recall is None
    ):
        balanced_accuracy = None
    else:
        balanced_accuracy = (
            pass_recall + fail_recall
        ) / 2

    return {
        "verified_candidates": len(verified),
        "runtime_pass_total": runtime_pass_total,
        "runtime_fail_total": runtime_fail_total,
        "protocol_failures": protocol_failures,
        "confusion_matrix": {
            "true_positive": tp,
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
        },
        "runtime_pass_recall": pass_recall,
        "runtime_fail_recall": fail_recall,
        "balanced_accuracy": balanced_accuracy,
    }


def summarize_condition(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    protocol_valid = [
        record
        for record in records
        if record["protocol_valid"]
    ]

    verified_metrics = summarize_verified(records)

    return {
        "candidates": len(records),
        "protocol_valid": len(protocol_valid),
        "accepts": sum(
            record["verdict"] == "accept"
            for record in records
        ),
        "rejects": sum(
            record["verdict"] == "reject"
            for record in records
        ),
        "mean_prompt_chars": mean(
            [
                float(record["prompt_chars"])
                for record in records
            ]
        ),
        "mean_response_chars": mean(
            [
                float(record["response_chars"])
                for record in records
            ]
        ),
        "mean_reason_chars": mean(
            [
                float(len(record["reason"]))
                for record in protocol_valid
                if isinstance(record["reason"], str)
            ]
        ),
        "total_model_seconds": sum(
            float(record["model_seconds"])
            for record in records
        ),
        "runtime_metrics": verified_metrics,
    }


def summarize(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for condition in REVIEW_CONDITIONS:
        selected = [
            record
            for record in records
            if record["review_condition"] == condition
        ]

        result[condition] = {
            "overall": summarize_condition(selected),
            "by_source_condition": {
                source_condition: summarize_condition(
                    [
                        record
                        for record in selected
                        if record["source_condition"]
                        == source_condition
                    ]
                )
                for source_condition in SOURCE_CONDITIONS
            },
        }

    return result


def print_corpus(
    candidates: list[Candidate],
) -> None:
    print("Frozen 008C corpus")
    print()

    for candidate in candidates:
        if candidate.runtime_pass is True:
            label = "RUNTIME_PASS"
        elif candidate.runtime_pass is False:
            label = "RUNTIME_FAIL"
        else:
            label = "NOT_RUNTIME_VERIFIED"

        print(
            candidate.candidate_id,
            f"syntax={candidate.syntax_valid}",
            label,
        )

    verified = verified_candidates(candidates)

    print()
    print("Committed candidates:", len(candidates))
    print("Runtime verified:", len(verified))
    print(
        "Runtime PASS:",
        sum(
            candidate.runtime_pass is True
            for candidate in verified
        ),
    )
    print(
        "Runtime FAIL:",
        sum(
            candidate.runtime_pass is False
            for candidate in verified
        ),
    )
    print(
        "Not runtime verified:",
        sum(
            candidate.runtime_pass is None
            for candidate in candidates
        ),
    )

    print()
    print("Calls by review condition:")
    for condition in REVIEW_CONDITIONS:
        print(
            f"  {condition}:",
            len(
                candidates_for_condition(
                    candidates,
                    condition,
                )
            ),
        )


def print_summary(
    summary: dict[str, Any],
) -> None:
    print()
    print("008C Summary")

    for condition in REVIEW_CONDITIONS:
        data = summary[condition]["overall"]
        runtime = data["runtime_metrics"]

        print()
        print(condition)
        print(
            "  protocol:",
            f"{data['protocol_valid']}"
            f"/{data['candidates']}",
        )
        print(
            "  runtime confusion:",
            runtime["confusion_matrix"],
        )
        print(
            "  runtime-pass recall:",
            runtime["runtime_pass_recall"],
        )
        print(
            "  runtime-fail recall:",
            runtime["runtime_fail_recall"],
        )
        print(
            "  balanced accuracy:",
            runtime["balanced_accuracy"],
        )
        print(
            "  accepts:",
            data["accepts"],
        )
        print(
            "  rejects:",
            data["rejects"],
        )
        print(
            "  mean prompt chars:",
            f"{data['mean_prompt_chars']:.1f}",
        )
        print(
            "  total model seconds:",
            f"{data['total_model_seconds']:.2f}",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument(
        "--validate-corpus",
        action="store_true",
    )
    args = parser.parse_args()

    candidates = load_corpus()
    validate_corpus(candidates)

    if args.validate_corpus:
        print_corpus(candidates)
        return

    if args.run_id is None:
        parser.error(
            "--run-id is required unless "
            "--validate-corpus is used"
        )

    normalize = load_normalizer()

    run_dir = RESULTS_ROOT / f"review-{args.run_id}"

    if run_dir.exists():
        raise FileExistsError(
            f"result directory already exists: {run_dir}"
        )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    records: list[dict[str, Any]] = []

    for review_condition in REVIEW_CONDITIONS:
        condition_candidates = (
            candidates_for_condition(
                candidates,
                review_condition,
            )
        )

        for candidate in condition_candidates:
            result_dir = (
                run_dir
                / review_condition
                / candidate.candidate_id
            )

            result_dir.mkdir(
                parents=True,
                exist_ok=False,
            )

            print(
                f"Reviewing "
                f"{candidate.candidate_id} "
                f"[{review_condition}]..."
            )

            record = evaluate_candidate(
                candidate=candidate,
                review_condition=review_condition,
                normalize=normalize,
                result_dir=result_dir,
            )

            records.append(record)

    summary = summarize(records)

    output = {
        "experiment": "008C",
        "run_id": args.run_id,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "source_run": "008B implementation-run-001",
        "reference_label": (
            "008B hidden runtime behavioral oracle"
        ),
        "ground_truth_limitation": (
            "runtime-oracle outcome is not "
            "complete task correctness"
        ),
        "conditions": list(REVIEW_CONDITIONS),
        "corpus": {
            "committed_candidates": len(candidates),
            "runtime_verified": len(
                verified_candidates(candidates)
            ),
            "runtime_pass": sum(
                candidate.runtime_pass is True
                for candidate in candidates
            ),
            "runtime_fail": sum(
                candidate.runtime_pass is False
                for candidate in candidates
            ),
            "not_runtime_verified": sum(
                candidate.runtime_pass is None
                for candidate in candidates
            ),
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

    print_summary(summary)


if __name__ == "__main__":
    main()