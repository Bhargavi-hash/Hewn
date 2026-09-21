from __future__ import annotations

import argparse
import hashlib
import json
import socket
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "research" / "012-running-models-locally"
RESULTS_DIR = MODULE_ROOT / "results"
LOG_DIR = RESULTS_DIR / "012g1-server-logs"

LLAMA_CPP_ROOT = Path.home() / "Documents" / "llama.cpp"
SERVER_BINARY = LLAMA_CPP_ROOT / "build" / "bin" / "llama-server"

HF_ROOT = Path.home() / ".cache" / "huggingface" / "hub"

HOST = "127.0.0.1"
PORT = 8080

THREADS = 4
CONTEXT_SIZE = 8192
PARALLEL = 1
TEMPERATURE = 0.0
MAX_TOKENS = 128

REPETITIONS = 5
TARGET_PROMPT_TOKENS = 1024

STARTUP_TIMEOUT_SECONDS = 120.0
REQUEST_TIMEOUT_SECONDS = 300.0

LLAMA_CPP_COMMIT = "930e2fa5995789efbf249a8bf61325bb626e417b"
LLAMA_CPP_VERSION = "0.4.1-dev (build 10991, commit 930e2fa59)"

HARDWARE_DESCRIPTION = (
    "Intel Core i5-10210U; 4 physical cores / 8 logical CPUs; "
    "~7.6 GiB RAM; no NVIDIA GPU; Linux x86_64"
)

SYSTEM_PROMPT = (
    "You are a programming assistant. Read the supplied source material "
    "and answer the final question concisely."
)


@dataclass(frozen=True)
class ModelCondition:
    label: str
    parameter_scale: str
    repository: str
    snapshot: str
    filename: str
    sha256: str
    expected_bytes: int

    @property
    def repository_cache(self) -> Path:
        return HF_ROOT / (
            "models--" + self.repository.replace("/", "--")
        )

    @property
    def snapshot_path(self) -> Path:
        return (
            self.repository_cache
            / "snapshots"
            / self.snapshot
            / self.filename
        )

    @property
    def model_id(self) -> str:
        return f"{self.repository}:Q4_K_M"


CONDITIONS = (
    ModelCondition(
        label="0.5B",
        parameter_scale="0.5B",
        repository="Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
        snapshot="ebb2015119c907b064c512bf053e945850b5875f",
        filename="qwen2.5-coder-0.5b-instruct-q4_k_m.gguf",
        sha256=(
            "1d9614638d18024d0fbb36575a15f130"
            "2a3adf044df10345688ec4f6e1c4ff32"
        ),
        expected_bytes=491400064,
    ),
    ModelCondition(
        label="1.5B",
        parameter_scale="1.5B",
        repository="Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        snapshot="f86cb2c1fa58255f8052cc32aeede1b7482d4361",
        filename="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        sha256=(
            "cc324af070c2ecbfd324a30884d2f951"
            "a7ff756aba85cb811a6ec436933bb046"
        ),
        expected_bytes=1117320768,
    ),
    ModelCondition(
        label="3B",
        parameter_scale="3B",
        repository="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
        snapshot="f74adce6aa16316c625447af059dbebe4983757c",
        filename="qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        sha256=(
            "724fb256bec1ff062b2f65e4569e871a"
            "d2e95ab2a3989723d1769c54294730b7"
        ),
        expected_bytes=2104932800,
    ),
)


@dataclass(frozen=True)
class ProcessMemory:
    vm_peak_kib: int | None
    vm_size_kib: int | None
    vm_hwm_kib: int | None
    vm_rss_kib: int | None
    rss_anon_kib: int | None
    rss_file_kib: int | None
    vm_data_kib: int | None
    vm_swap_kib: int | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def validate_artifact(condition: ModelCondition) -> Path:
    path = condition.snapshot_path

    if not path.exists():
        raise RuntimeError(
            f"{condition.label}: expected artifact does not exist: {path}"
        )

    resolved = path.resolve()

    actual_bytes = resolved.stat().st_size
    if actual_bytes != condition.expected_bytes:
        raise RuntimeError(
            f"{condition.label}: artifact size mismatch: "
            f"expected {condition.expected_bytes}, got {actual_bytes}"
        )

    actual_hash = sha256_file(resolved)
    if actual_hash != condition.sha256:
        raise RuntimeError(
            f"{condition.label}: artifact SHA-256 mismatch: "
            f"expected {condition.sha256}, got {actual_hash}"
        )

    return resolved


def read_status_value(
    values: dict[str, int],
    key: str,
) -> int | None:
    return values.get(key)


def read_process_memory(pid: int) -> ProcessMemory:
    path = Path(f"/proc/{pid}/status")

    values: dict[str, int] = {}

    for line in path.read_text().splitlines():
        if ":" not in line:
            continue

        key, remainder = line.split(":", 1)
        fields = remainder.strip().split()

        if not fields:
            continue

        try:
            values[key] = int(fields[0])
        except ValueError:
            continue

    return ProcessMemory(
        vm_peak_kib=read_status_value(values, "VmPeak"),
        vm_size_kib=read_status_value(values, "VmSize"),
        vm_hwm_kib=read_status_value(values, "VmHWM"),
        vm_rss_kib=read_status_value(values, "VmRSS"),
        rss_anon_kib=read_status_value(values, "RssAnon"),
        rss_file_kib=read_status_value(values, "RssFile"),
        vm_data_kib=read_status_value(values, "VmData"),
        vm_swap_kib=read_status_value(values, "VmSwap"),
    )


def port_is_free() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, PORT))
        except OSError:
            return False

    return True

def wait_for_port_free(timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if port_is_free():
            return

        time.sleep(0.25)

    raise RuntimeError(
        f"Port {PORT} did not become reusable within "
        f"{timeout_seconds:.0f} seconds"
    )


def server_is_ready() -> bool:
    url = f"http://{HOST}:{PORT}/health"

    try:
        with urllib.request.urlopen(
            url,
            timeout=2.0,
        ) as response:
            return bool(response.status == 200)
    except (urllib.error.URLError, TimeoutError):
        return False


def wait_for_server(process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        return_code = process.poll()

        if return_code is not None:
            raise RuntimeError(
                "llama-server exited during startup with "
                f"return code {return_code}"
            )

        if server_is_ready():
            return

        time.sleep(0.5)

    raise RuntimeError(
        f"llama-server did not become healthy within "
        f"{STARTUP_TIMEOUT_SECONDS:.0f} seconds"
    )


def start_server(
    condition: ModelCondition,
    artifact: Path,
    repetition: int,
) -> tuple[subprocess.Popen[str], Any, Path]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = (
        LOG_DIR
        / f"{condition.label.lower().replace('.', '_')}"
        f"-run{repetition}-server.log"
    )
    log_handle = log_path.open("w", encoding="utf-8")

    command = [
        str(SERVER_BINARY),
        "-m",
        str(artifact),
        "-t",
        str(THREADS),
        "-c",
        str(CONTEXT_SIZE),
        "--parallel",
        str(PARALLEL),
        "--no-cache-prompt",
        "--metrics",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ]

    process = subprocess.Popen(
        command,
        cwd=LLAMA_CPP_ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_server(process)
    except Exception:
        process.terminate()

        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

        log_handle.close()
        raise

    return process, log_handle, log_path


def stop_server(
    process: subprocess.Popen[str],
    log_handle: Any,
) -> None:
    if process.poll() is None:
        process.terminate()

        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    log_handle.close()


def post_json(
    endpoint: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], float]:
    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()

    with urllib.request.urlopen(
        request,
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        raw = response.read()

    wall_seconds = time.perf_counter() - started

    decoded = json.loads(raw.decode("utf-8"))

    if not isinstance(decoded, dict):
        raise TypeError("Expected llama.cpp response to be a JSON object")

    return cast(dict[str, Any], decoded), wall_seconds


def chat_request(
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
) -> tuple[dict[str, Any], float]:
    return post_json(
        f"http://{HOST}:{PORT}/v1/chat/completions",
        {
            "model": "local-model",
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": max_tokens,
            "stream": False,
        },
    )


def extract_usage(response: dict[str, Any]) -> dict[str, Any]:
    usage = response.get("usage")

    if not isinstance(usage, dict):
        raise TypeError("Response does not contain a usage object")

    return cast(dict[str, Any], usage)


def prompt_tokens_from_response(response: dict[str, Any]) -> int:
    usage = extract_usage(response)
    value = usage.get("prompt_tokens")

    if not isinstance(value, int):
        raise TypeError("usage.prompt_tokens is missing or not an integer")

    return value


def completion_tokens_from_response(response: dict[str, Any]) -> int:
    usage = extract_usage(response)
    value = usage.get("completion_tokens")

    if not isinstance(value, int):
        raise TypeError(
            "usage.completion_tokens is missing or not an integer"
        )

    return value


def cached_prompt_tokens(response: dict[str, Any]) -> int | None:
    usage = extract_usage(response)

    details = usage.get("prompt_tokens_details")

    if isinstance(details, dict):
        cached = details.get("cached_tokens")

        if isinstance(cached, int):
            return cached

    timings = response.get("timings")

    if isinstance(timings, dict):
        cached = timings.get("prompt_n_cached")

        if isinstance(cached, int):
            return cached

    return None


def response_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")

    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Response contains no choices")

    choice = choices[0]

    if not isinstance(choice, dict):
        raise TypeError("Response choice is not an object")

    message = choice.get("message")

    if not isinstance(message, dict):
        raise TypeError("Response choice contains no message")

    content = message.get("content")

    if not isinstance(content, str):
        raise TypeError("Response message content is not a string")

    return content


def finish_reason(response: dict[str, Any]) -> str | None:
    choices = response.get("choices")

    if not isinstance(choices, list) or not choices:
        return None

    choice = choices[0]

    if not isinstance(choice, dict):
        return None

    value = choice.get("finish_reason")

    return value if isinstance(value, str) else None


def timing_value(
    response: dict[str, Any],
    key: str,
) -> int | float | None:
    timings = response.get("timings")

    if not isinstance(timings, dict):
        return None

    value = timings.get(key)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value

    return None


def calibrate_prompt() -> tuple[str, int]:
    """
    Build a deterministic prompt whose *chat-formatted* prompt token count
    is exactly TARGET_PROMPT_TOKENS according to the running llama.cpp model.

    Calibration happens independently for every fresh model process because
    tokenization/chat-template accounting is part of the model artifact.
    """

    prefix = (
        "Study the following synthetic Python repository notes. "
        "The repeated records are intentionally redundant so that this "
        "experiment measures prompt-processing work rather than retrieval.\n\n"
    )

    suffix = (
        "\n\nQuestion: Which function is responsible for validating a "
        "repository-relative path? Answer in one short sentence."
    )

    record = (
        "\nRepository record: workspace.py defines validate_relative_path, "
        "which resolves a candidate path and verifies that it remains "
        "inside the configured repository root. repository.py builds a "
        "structural index. retrieval.py ranks candidate source locations. "
        "execution.py runs approved verification commands."
    )

    low = 0
    high = 1

    def candidate(count: int) -> str:
        return prefix + (record * count) + suffix

    def count_tokens(text: str) -> int:
        response, _ = chat_request(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=1,
        )
        return prompt_tokens_from_response(response)

    while count_tokens(candidate(high)) < TARGET_PROMPT_TOKENS:
        low = high
        high *= 2

        if high > 4096:
            raise RuntimeError("Unable to bracket target prompt token count")

    best_text: str | None = None
    best_tokens: int | None = None

    while low <= high:
        middle = (low + high) // 2
        text = candidate(middle)
        tokens = count_tokens(text)

        if tokens == TARGET_PROMPT_TOKENS:
            return text, tokens

        if best_tokens is None or abs(tokens - TARGET_PROMPT_TOKENS) < abs(
            best_tokens - TARGET_PROMPT_TOKENS
        ):
            best_text = text
            best_tokens = tokens

        if tokens < TARGET_PROMPT_TOKENS:
            low = middle + 1
        else:
            high = middle - 1

    if best_text is None or best_tokens is None:
        raise RuntimeError("Prompt calibration produced no candidate")

    # Repeated whole records may skip over exactly 1024 tokens. Add a
    # deterministic token-padding tail one word at a time and re-measure.
    text = best_text
    tokens = best_tokens

    if tokens > TARGET_PROMPT_TOKENS:
        raise RuntimeError(
            "Nearest calibrated prompt exceeded target; "
            f"got {tokens}, target {TARGET_PROMPT_TOKENS}"
        )

    padding_index = 0

    while tokens < TARGET_PROMPT_TOKENS:
        padding_index += 1
        text += f" pad{padding_index}"
        tokens = count_tokens(text)

        if tokens > TARGET_PROMPT_TOKENS:
            raise RuntimeError(
                "Padding crossed the target token count: "
                f"got {tokens}, target {TARGET_PROMPT_TOKENS}"
            )

        if padding_index > 4096:
            raise RuntimeError("Prompt padding failed to converge")

    return text, tokens


def validate_response(
    response: dict[str, Any],
    *,
    expected_prompt_tokens: int,
) -> None:
    prompt_tokens = prompt_tokens_from_response(response)
    completion_tokens = completion_tokens_from_response(response)

    usage = extract_usage(response)
    total_tokens = usage.get("total_tokens")

    if not isinstance(total_tokens, int):
        raise TypeError("usage.total_tokens is missing or not an integer")

    if prompt_tokens != expected_prompt_tokens:
        raise RuntimeError(
            f"Prompt token mismatch: expected {expected_prompt_tokens}, "
            f"got {prompt_tokens}"
        )

    if prompt_tokens + completion_tokens != total_tokens:
        raise RuntimeError(
            "Token accounting failed: "
            f"{prompt_tokens} + {completion_tokens} != {total_tokens}"
        )

    cached = cached_prompt_tokens(response)

    if cached is not None and cached != 0:
        raise RuntimeError(
            f"Prompt cache was expected to be disabled, got {cached} "
            "cached prompt tokens"
        )


def run_observation(
    condition: ModelCondition,
    artifact: Path,
    repetition: int,
) -> dict[str, Any]:
    wait_for_port_free()

    process, log_handle, log_path = start_server(
        condition,
        artifact,
        repetition,
    )

    try:
        # Memory is sampled immediately after the fresh server becomes
        # healthy, before calibration or measured inference.
        fresh_memory = read_process_memory(process.pid)

        prompt, calibrated_tokens = calibrate_prompt()

        if calibrated_tokens != TARGET_PROMPT_TOKENS:
            raise RuntimeError(
                f"Calibration failed: expected {TARGET_PROMPT_TOKENS}, "
                f"got {calibrated_tokens}"
            )

        # Calibration itself has executed requests, so this second sample is
        # deliberately retained separately. It must not be called fresh idle.
        before_measured_request = read_process_memory(process.pid)

        response, wall_seconds = chat_request(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=MAX_TOKENS,
        )

        validate_response(
            response,
            expected_prompt_tokens=TARGET_PROMPT_TOKENS,
        )

        after_request = read_process_memory(process.pid)

        prompt_ms = timing_value(response, "prompt_ms")
        predicted_ms = timing_value(response, "predicted_ms")

        prompt_seconds = (
            float(prompt_ms) / 1000.0
            if prompt_ms is not None
            else None
        )
        generation_seconds = (
            float(predicted_ms) / 1000.0
            if predicted_ms is not None
            else None
        )

        result = {
            "experiment": "012G-1",
            "independent_variable": "model_size",
            "condition": {
                **asdict(condition),
                "artifact_path": str(condition.snapshot_path),
                "resolved_artifact_path": str(artifact),
                "artifact_mib": condition.expected_bytes / (1024**2),
            },
            "provenance": {
                "llama_cpp_commit": LLAMA_CPP_COMMIT,
                "llama_cpp_version": LLAMA_CPP_VERSION,
                "hardware": HARDWARE_DESCRIPTION,
                "repetition": repetition,
            },
            "configuration": {
                "quantization": "Q4_K_M",
                "threads": THREADS,
                "configured_context": CONTEXT_SIZE,
                "target_prompt_tokens": TARGET_PROMPT_TOKENS,
                "prompt_cache_enabled": False,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "parallel": PARALLEL,
                "fresh_server_process": True,
            },
            "measurements": {
                "prompt_tokens": prompt_tokens_from_response(response),
                "completion_tokens": completion_tokens_from_response(response),
                "cached_prompt_tokens": cached_prompt_tokens(response),
                "finish_reason": finish_reason(response),
                "content": response_content(response),
                "prompt_seconds": prompt_seconds,
                "prompt_tokens_per_second": timing_value(
                    response,
                    "prompt_per_second",
                ),
                "generation_seconds": generation_seconds,
                "generation_tokens_per_second": timing_value(
                    response,
                    "predicted_per_second",
                ),
                "wall_seconds": wall_seconds,
                "fresh_process_memory": asdict(fresh_memory),
                "before_measured_request_memory": asdict(
                    before_measured_request
                ),
                "after_request_memory": asdict(after_request),
            },
            "raw_response": response,
            "server_log": str(log_path),
        }

        

        return result

    finally:
        stop_server(process, log_handle)


def result_path(
    condition: ModelCondition,
    repetition: int,
) -> Path:
    label = condition.label.lower().replace(".", "_")

    return RESULTS_DIR / f"012g1-{label}-run{repetition}.json"

def load_existing_result(
    condition: ModelCondition,
    repetition: int,
) -> dict[str, Any] | None:
    path = result_path(condition, repetition)

    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise TypeError(
            f"Existing observation is not a JSON object: {path}"
        )

    result = cast(dict[str, Any], payload)

    if result.get("experiment") != "012G-1":
        raise RuntimeError(
            f"Existing observation has wrong experiment: {path}"
        )

    condition_value = result.get("condition")
    provenance_value = result.get("provenance")
    configuration_value = result.get("configuration")
    measurements_value = result.get("measurements")

    if not isinstance(condition_value, dict):
        raise TypeError(
            f"Existing observation has invalid condition: {path}"
        )

    if not isinstance(provenance_value, dict):
        raise TypeError(
            f"Existing observation has invalid provenance: {path}"
        )

    if not isinstance(configuration_value, dict):
        raise TypeError(
            f"Existing observation has invalid configuration: {path}"
        )

    if not isinstance(measurements_value, dict):
        raise TypeError(
            f"Existing observation has invalid measurements: {path}"
        )

    expected_condition = {
        "label": condition.label,
        "parameter_scale": condition.parameter_scale,
        "repository": condition.repository,
        "snapshot": condition.snapshot,
        "filename": condition.filename,
        "sha256": condition.sha256,
        "expected_bytes": condition.expected_bytes,
    }

    for key, expected in expected_condition.items():
        if condition_value.get(key) != expected:
            raise RuntimeError(
                f"Existing observation condition mismatch for {key}: "
                f"{path}"
            )

    if provenance_value.get("repetition") != repetition:
        raise RuntimeError(
            f"Existing observation repetition mismatch: {path}"
        )

    expected_configuration = {
        "quantization": "Q4_K_M",
        "threads": THREADS,
        "configured_context": CONTEXT_SIZE,
        "target_prompt_tokens": TARGET_PROMPT_TOKENS,
        "prompt_cache_enabled": False,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "parallel": PARALLEL,
        "fresh_server_process": True,
    }

    for key, expected in expected_configuration.items():
        if configuration_value.get(key) != expected:
            raise RuntimeError(
                f"Existing observation configuration mismatch for {key}: "
                f"{path}"
            )

    if measurements_value.get("prompt_tokens") != TARGET_PROMPT_TOKENS:
        raise RuntimeError(
            f"Existing observation prompt-token mismatch: {path}"
        )

    cached = measurements_value.get("cached_prompt_tokens")

    if cached is not None and cached != 0:
        raise RuntimeError(
            f"Existing observation contains cached prompt tokens: {path}"
        )

    return result

def write_result(
    condition: ModelCondition,
    repetition: int,
    result: dict[str, Any],
) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    path = result_path(condition, repetition)

    if path.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing observation: {path}"
        )

    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return path


def summarize(results: list[dict[str, Any]]) -> None:
    print()
    print("012G-1 SYSTEMS SUMMARY")
    print()
    print(
        "model | n | artifact_MiB | prompt_s_med | prompt_tps_med | "
        "decode_tps_med | wall_s_med | fresh_rss_MiB_med | swap_MiB_med"
    )
    print("-" * 116)

    by_model: dict[str, list[dict[str, Any]]] = {}

    for result in results:
        condition_value = result.get("condition")

        if not isinstance(condition_value, dict):
            raise TypeError("Result condition is not an object")

        label_value = condition_value.get("label")

        if not isinstance(label_value, str):
            raise TypeError("Result condition label is not a string")

        by_model.setdefault(label_value, []).append(result)

    for condition in CONDITIONS:
        model_rows = by_model.get(condition.label, [])

        if not model_rows:
            continue

        prompt_seconds: list[float] = []
        prompt_tps: list[float] = []
        decode_tps: list[float] = []
        wall_seconds: list[float] = []
        rss_values: list[float] = []
        swap_values: list[float] = []

        for row in model_rows:
            measurements_value = row.get("measurements")

            if not isinstance(measurements_value, dict):
                raise TypeError("Result measurements is not an object")

            numeric_fields = (
                ("prompt_seconds", prompt_seconds),
                ("prompt_tokens_per_second", prompt_tps),
                ("generation_tokens_per_second", decode_tps),
                ("wall_seconds", wall_seconds),
            )

            for field_name, destination in numeric_fields:
                value = measurements_value.get(field_name)

                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                ):
                    destination.append(float(value))

            memory_value = measurements_value.get(
                "fresh_process_memory"
            )

            if not isinstance(memory_value, dict):
                raise TypeError(
                    "fresh_process_memory is not an object"
                )

            rss = memory_value.get("vm_rss_kib")
            swap = memory_value.get("vm_swap_kib")

            if isinstance(rss, int) and not isinstance(rss, bool):
                rss_values.append(rss / 1024.0)

            if isinstance(swap, int) and not isinstance(swap, bool):
                swap_values.append(swap / 1024.0)

        def format_median(values: list[float]) -> str:
            if not values:
                return "NA"

            return f"{statistics.median(values):.2f}"

        print(
            f"{condition.label:>5} | "
            f"{len(model_rows):>1} | "
            f"{condition.expected_bytes / (1024**2):>12.1f} | "
            f"{format_median(prompt_seconds):>12} | "
            f"{format_median(prompt_tps):>14} | "
            f"{format_median(decode_tps):>14} | "
            f"{format_median(wall_seconds):>10} | "
            f"{format_median(rss_values):>17} | "
            f"{format_median(swap_values):>12}"
        )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Module 12 012G-1 model-size systems experiment."
    )

    parser.add_argument(
        "--models",
        nargs="+",
        choices=[condition.label for condition in CONDITIONS],
        default=[condition.label for condition in CONDITIONS],
        help="Model-size conditions to run.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not SERVER_BINARY.exists():
        raise RuntimeError(
            f"llama-server binary does not exist: {SERVER_BINARY}"
        )

    selected = [
        condition
        for condition in CONDITIONS
        if condition.label in args.models
    ]

    artifacts: dict[str, Path] = {}

    print("Validating frozen model artifacts...")

    for condition in selected:
        artifact = validate_artifact(condition)
        artifacts[condition.label] = artifact

        print(
            f"  {condition.label}: "
            f"{condition.expected_bytes / (1024**2):.1f} MiB "
            f"sha256={condition.sha256}"
        )

    print()
    print(
        f"Running {len(selected)} model-size conditions × "
        f"{REPETITIONS} repetitions."
    )
    print("Each observation uses a fresh llama-server process.")
    print()

    completed: list[dict[str, Any]] = []

    for condition in selected:
        for repetition in range(1, REPETITIONS + 1):
            print(
                f"[{condition.label}] repetition "
                f"{repetition}/{REPETITIONS}"
            )

            existing = load_existing_result(
                condition,
                repetition,
            )

            if existing is not None:
                path = result_path(condition, repetition)
                completed.append(existing)
                print(f"  validated existing observation: {path}")
                continue

            result = run_observation(
                condition,
                artifacts[condition.label],
                repetition,
            )

            path = write_result(
                condition,
                repetition,
                result,
            )

            completed.append(result)

            measurements = result["measurements"]

            print(
                "  "
                f"prompt={measurements['prompt_tokens']} "
                f"completion={measurements['completion_tokens']} "
                f"prefill={measurements['prompt_seconds']!r}s "
                f"decode_tps="
                f"{measurements['generation_tokens_per_second']!r} "
                f"wall={measurements['wall_seconds']:.2f}s"
            )
            print(f"  wrote {path}")

    summarize(completed)

    print()
    print(
        f"012G-1 complete: {len(completed)} validated observations."
    )


if __name__ == "__main__":
    main()