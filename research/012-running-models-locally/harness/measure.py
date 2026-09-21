from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .process_memory import ProcessMemory, read_process_memory

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Provenance:
    runtime: str
    runtime_commit: str
    runtime_version: str
    runtime_build: str
    model_id: str
    quantization: str
    hardware_description: str


@dataclass(frozen=True)
class InferenceConfiguration:
    base_url: str
    threads: int
    configured_context: int
    prompt_cache_enabled: bool
    temperature: float
    max_tokens: int


@dataclass(frozen=True)
class MemoryMeasurements:
    server_pid: int
    before_request: ProcessMemory
    after_request: ProcessMemory


@dataclass(frozen=True)
class Measurements:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cached_prompt_tokens: int | None
    prompt_evaluated_tokens: int | None
    generated_tokens: int | None
    prompt_seconds: float | None
    generation_seconds: float | None
    prompt_tokens_per_second: float | None
    generation_tokens_per_second: float | None
    wall_time_seconds: float
    finish_reason: str | None


@dataclass(frozen=True)
class AccountingValidation:
    total_token_accounting: bool | None
    prompt_cache_accounting: bool | None
    generation_token_accounting: bool | None

    @property
    def all_observed_valid(self) -> bool:
        observed = (
            self.total_token_accounting,
            self.prompt_cache_accounting,
            self.generation_token_accounting,
        )
        return all(value is not False for value in observed)


@dataclass(frozen=True)
class InferenceRun:
    provenance: Provenance
    configuration: InferenceConfiguration
    measurements: Measurements
    accounting: AccountingValidation
    memory: MemoryMeasurements | None
    raw_response: JsonObject


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _optional_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _mapping(value: object) -> JsonObject:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _validate_sum(
    left: int | None,
    right: int | None,
    expected: int | None,
) -> bool | None:
    if left is None or right is None or expected is None:
        return None
    return left + right == expected


def _validate_equal(
    left: int | None,
    right: int | None,
) -> bool | None:
    if left is None or right is None:
        return None
    return left == right


def normalize_response(
    *,
    response: JsonObject,
    wall_time_seconds: float,
) -> tuple[Measurements, AccountingValidation]:
    usage = _mapping(response.get("usage"))
    prompt_details = _mapping(usage.get("prompt_tokens_details"))
    timings = _mapping(response.get("timings"))

    prompt_tokens = _optional_int(usage.get("prompt_tokens"))
    completion_tokens = _optional_int(usage.get("completion_tokens"))
    total_tokens = _optional_int(usage.get("total_tokens"))

    cached_prompt_tokens = _optional_int(prompt_details.get("cached_tokens"))
    prompt_evaluated_tokens = _optional_int(timings.get("prompt_n"))
    generated_tokens = _optional_int(timings.get("predicted_n"))

    prompt_ms = _optional_float(timings.get("prompt_ms"))
    generation_ms = _optional_float(timings.get("predicted_ms"))

    choices = response.get("choices")
    finish_reason: str | None = None

    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            finish_reason = _optional_str(first_choice.get("finish_reason"))

    measurements = Measurements(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached_prompt_tokens=cached_prompt_tokens,
        prompt_evaluated_tokens=prompt_evaluated_tokens,
        generated_tokens=generated_tokens,
        prompt_seconds=None if prompt_ms is None else prompt_ms / 1000.0,
        generation_seconds=(
            None if generation_ms is None else generation_ms / 1000.0
        ),
        prompt_tokens_per_second=_optional_float(
            timings.get("prompt_per_second")
        ),
        generation_tokens_per_second=_optional_float(
            timings.get("predicted_per_second")
        ),
        wall_time_seconds=wall_time_seconds,
        finish_reason=finish_reason,
    )

    accounting = AccountingValidation(
        total_token_accounting=_validate_sum(
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ),
        prompt_cache_accounting=_validate_sum(
            cached_prompt_tokens,
            prompt_evaluated_tokens,
            prompt_tokens,
        ),
        generation_token_accounting=_validate_equal(
            generated_tokens,
            completion_tokens,
        ),
    )

    return measurements, accounting


def request_completion(
    *,
    configuration: InferenceConfiguration,
    model_id: str,
    prompt: str,
    timeout_seconds: float,
) -> tuple[JsonObject, float]:
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": configuration.temperature,
        "max_tokens": configuration.max_tokens,
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        f"{configuration.base_url.rstrip('/')}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            response_body = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"llama.cpp request failed: {exc}") from exc

    wall_time_seconds = time.perf_counter() - start

    parsed = json.loads(response_body)
    if not isinstance(parsed, dict):
        raise TypeError("llama.cpp response must be a JSON object")

    return _mapping(parsed), wall_time_seconds


def measure(
    *,
    provenance: Provenance,
    configuration: InferenceConfiguration,
    prompt: str,
    timeout_seconds: float = 120.0,
    server_pid: int | None = None,
) -> InferenceRun:
    memory_before = (
        read_process_memory(server_pid)
        if server_pid is not None
        else None
    )

    response, wall_time_seconds = request_completion(
        configuration=configuration,
        model_id=provenance.model_id,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
    )

    memory_after = (
        read_process_memory(server_pid)
        if server_pid is not None
        else None
    )

    measurements, accounting = normalize_response(
        response=response,
        wall_time_seconds=wall_time_seconds,
    )

    memory: MemoryMeasurements | None = None

    if (
        server_pid is not None
        and memory_before is not None
        and memory_after is not None
    ):
        memory = MemoryMeasurements(
            server_pid=server_pid,
            before_request=memory_before,
            after_request=memory_after,
        )

    return InferenceRun(
        provenance=provenance,
        configuration=configuration,
        measurements=measurements,
        accounting=accounting,
        memory=memory,
        raw_response=response,
    )


def write_run(run: InferenceRun, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(asdict(run), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure one llama.cpp chat-completion request."
    )

    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", required=True)

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
    )
    parser.add_argument("--threads", type=int, required=True)
    parser.add_argument("--context", type=int, required=True)

    parser.add_argument(
        "--prompt-cache",
        choices=("enabled", "disabled"),
        required=True,
        help=(
            "Prompt-cache state of the llama.cpp server. "
            "This records the experimental configuration; it does not "
            "change the server setting."
        ),
    )

    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=64)

    parser.add_argument("--runtime-commit", required=True)
    parser.add_argument("--runtime-version", required=True)
    parser.add_argument("--runtime-build", required=True)

    parser.add_argument("--model-id", required=True)
    parser.add_argument("--quantization", required=True)
    parser.add_argument("--hardware", required=True)

    parser.add_argument(
        "--server-pid",
        type=int,
        default=None,
        help=(
            "Explicit llama-server PID used for Linux process-memory "
            "measurements."
        ),
    )

    parser.add_argument("--timeout", type=float, default=120.0)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    provenance = Provenance(
        runtime="llama.cpp",
        runtime_commit=args.runtime_commit,
        runtime_version=args.runtime_version,
        runtime_build=args.runtime_build,
        model_id=args.model_id,
        quantization=args.quantization,
        hardware_description=args.hardware,
    )

    configuration = InferenceConfiguration(
        base_url=args.base_url,
        threads=args.threads,
        configured_context=args.context,
        prompt_cache_enabled=args.prompt_cache == "enabled",
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    run = measure(
        provenance=provenance,
        configuration=configuration,
        prompt=args.prompt,
        timeout_seconds=args.timeout,
        server_pid=args.server_pid,
    )

    write_run(run, args.output)

    print(json.dumps(asdict(run), indent=2, sort_keys=True))

    if not run.accounting.all_observed_valid:
        raise SystemExit("observed llama.cpp accounting invariant failed")


if __name__ == "__main__":
    main()