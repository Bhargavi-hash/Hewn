from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, cast

REPO_ROOT = Path(__file__).resolve().parents[2]

LLAMA_CPP_ROOT = Path.home() / "Documents" / "llama.cpp"
SERVER_BINARY = LLAMA_CPP_ROOT / "build" / "bin" / "llama-server"

MODULE_ROOT = REPO_ROOT / "research" / "012-running-models-locally"
TASKS_PATH = MODULE_ROOT / "012f2-tasks.json"
RESULTS_DIR = MODULE_ROOT / "results"
LOG_DIR = RESULTS_DIR / "012f2-server-logs"

HF_CACHE_ROOT = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--Qwen--Qwen2.5-Coder-1.5B-Instruct-GGUF"
)

HF_SNAPSHOT = (
    HF_CACHE_ROOT
    / "snapshots"
    / "f86cb2c1fa58255f8052cc32aeede1b7482d4361"
)

HF_REPOSITORY = "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"

RUNTIME_COMMIT = "930e2fa5995789efbf249a8bf61325bb626e417b"
RUNTIME_VERSION = "0.4.1-dev"
RUNTIME_BUILD = "build 10991, commit 930e2fa59"

HARDWARE_DESCRIPTION = (
    "Intel Core i5-10210U, 4 physical cores / 8 logical CPUs, "
    "~7.6 GiB RAM, no NVIDIA GPU"
)

THREADS = 4
CONFIGURED_CONTEXT = 8192
MAX_TOKENS = 128
PORT = 8080

REQUEST_TIMEOUT_SECONDS = 300.0
STARTUP_TIMEOUT_SECONDS = 120.0

SYSTEM_PROMPT = (
    "You are being evaluated on a programming reasoning task. "
    "Follow the requested response protocol exactly."
)


@dataclass(frozen=True, slots=True)
class QuantizationCondition:
    quantization: str
    filename: str
    blob_hash: str
    expected_artifact_bytes: int

    @property
    def model_id(self) -> str:
        return f"{HF_REPOSITORY}:{self.quantization}"

    @property
    def snapshot_path(self) -> Path:
        return HF_SNAPSHOT / self.filename

    @property
    def blob_path(self) -> Path:
        return HF_CACHE_ROOT / "blobs" / self.blob_hash


CONDITIONS = (
    QuantizationCondition(
        quantization="Q3_K_M",
        filename="qwen2.5-coder-1.5b-instruct-q3_k_m.gguf",
        blob_hash=(
            "d281a3a0010df03c8a0e3ffebd7f9444a95244fb518f132c5475e4b48d9adb5e"
        ),
        expected_artifact_bytes=924_456_000,
    ),
    QuantizationCondition(
        quantization="Q4_K_M",
        filename="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        blob_hash=(
            "cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046"
        ),
        expected_artifact_bytes=1_117_320_768,
    ),
    QuantizationCondition(
        quantization="Q5_K_M",
        filename="qwen2.5-coder-1.5b-instruct-q5_k_m.gguf",
        blob_hash=(
            "f15d02e8e51a5c6f9448b972819acfa66aee4d8bb7d881a8b8ba3d90da08ef09"
        ),
        expected_artifact_bytes=1_285_494_336,
    ),
    QuantizationCondition(
        quantization="Q6_K",
        filename="qwen2.5-coder-1.5b-instruct-q6_k.gguf",
        blob_hash=(
            "9b05dce8089197c866b9f76e1db45de8617cda98d9d06059958cb8ad32c56dfa"
        ),
        expected_artifact_bytes=1_464_178_752,
    ),
    QuantizationCondition(
        quantization="Q8_0",
        filename="qwen2.5-coder-1.5b-instruct-q8_0.gguf",
        blob_hash=(
            "507de59046601282ba768a9789900e6ccf60ed93ddf346730b7c68eb0715bc47"
        ),
        expected_artifact_bytes=1_894_532_160,
    ),
)


def load_manifest() -> dict[str, Any]:
    raw_payload = json.loads(
        TASKS_PATH.read_text(encoding="utf-8")
    )

    if not isinstance(raw_payload, dict):
        raise TypeError(
            "task manifest must be a JSON object"
        )

    payload = cast(dict[str, Any], raw_payload)

    if payload.get("experiment") != "012F-2":
        raise ValueError("unexpected experiment identifier")

    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 10:
        raise ValueError("expected exactly 10 frozen tasks")

    protocol = payload.get("response_protocol")
    if not isinstance(protocol, dict):
        raise TypeError("missing response protocol")

    instruction = protocol.get("instruction")
    if not isinstance(instruction, str) or not instruction:
        raise ValueError(
            "missing response protocol instruction"
        )

    return payload

def validate_artifact(condition: QuantizationCondition) -> None:
    snapshot_path = condition.snapshot_path

    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"{condition.quantization}: missing snapshot artifact: "
            f"{snapshot_path}"
        )

    if not snapshot_path.is_symlink():
        raise ValueError(
            f"{condition.quantization}: expected snapshot artifact "
            "to be a symlink"
        )

    resolved = snapshot_path.resolve()

    if resolved != condition.blob_path:
        raise ValueError(
            f"{condition.quantization}: artifact resolved to "
            f"{resolved}, expected {condition.blob_path}"
        )

    size = resolved.stat().st_size

    if size != condition.expected_artifact_bytes:
        raise ValueError(
            f"{condition.quantization}: artifact size {size}, "
            f"expected {condition.expected_artifact_bytes}"
        )


def server_is_ready() -> bool:
    url = f"http://127.0.0.1:{PORT}/health"

    try:
        with urllib.request.urlopen(
            url,
            timeout=1.0,
        ) as response:
            return bool(response.status == 200)
    except (
        urllib.error.URLError,
        TimeoutError,
    ):
        return False


def ensure_port_is_free() -> None:
    if server_is_ready():
        raise RuntimeError(
            f"port {PORT} already has a responding llama.cpp server"
        )


def wait_for_server(process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"llama-server exited during startup "
                f"with code {process.returncode}"
            )

        if server_is_ready():
            return

        time.sleep(0.25)

    raise TimeoutError(
        f"llama-server did not become ready within "
        f"{STARTUP_TIMEOUT_SECONDS:.0f}s"
    )


def start_server(
    condition: QuantizationCondition,
) -> tuple[subprocess.Popen[bytes], BinaryIO]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = (
        LOG_DIR
        / f"{condition.quantization.lower()}-server.log"
    )

    log_handle = log_path.open("wb")

    command = [
        str(SERVER_BINARY),
        "-hf",
        condition.model_id,
        "-t",
        str(THREADS),
        "-c",
        str(CONFIGURED_CONTEXT),
        "--parallel",
        "1",
        "--no-cache-prompt",
        "--metrics",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ]

    process = subprocess.Popen(
        command,
        cwd=LLAMA_CPP_ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    try:
        wait_for_server(process)
    except BaseException:
        stop_server(process)
        log_handle.close()
        raise

    return process, log_handle


def stop_server(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=15)


def build_user_prompt(
    task: dict[str, Any],
    protocol_instruction: str,
) -> str:
    task_prompt = task.get("prompt")

    if not isinstance(task_prompt, str) or not task_prompt:
        raise ValueError(
            f"{task.get('task_id')}: missing task prompt"
        )

    return (
        f"{task_prompt}\n\n"
        "Response protocol:\n"
        f"{protocol_instruction}"
    )


def request_completion(
    *,
    condition: QuantizationCondition,
    task: dict[str, Any],
    protocol_instruction: str,
) -> dict[str, Any]:
    user_prompt = build_user_prompt(
        task,
        protocol_instruction,
    )

    request_payload = {
        "model": condition.model_id,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }

    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()

    with urllib.request.urlopen(
        request,
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        raw_body = response.read()

    wall_time_seconds = time.perf_counter() - started

    response_payload = json.loads(
        raw_body.decode("utf-8")
    )

    return {
        "request": {
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": user_prompt,
            "temperature": 0.0,
            "max_tokens": MAX_TOKENS,
        },
        "response": response_payload,
        "wall_time_seconds": wall_time_seconds,
    }


def extract_measurements(
    response_payload: dict[str, Any],
) -> dict[str, Any]:
    usage = response_payload.get("usage", {})
    timings = response_payload.get("timings", {})

    choices = response_payload.get("choices", [])

    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError(
            "expected exactly one completion choice"
        )

    choice = choices[0]
    message = choice.get("message", {})

    content = message.get("content")
    if not isinstance(content, str):
        raise TypeError("completion content is not a string")

    prompt_details = usage.get(
        "prompt_tokens_details",
        {},
    )

    return {
        "content": content,
        "finish_reason": choice.get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get(
            "completion_tokens"
        ),
        "total_tokens": usage.get("total_tokens"),
        "cached_prompt_tokens": prompt_details.get(
            "cached_tokens"
        ),
        "prompt_seconds": (
            timings.get("prompt_ms") / 1000
            if isinstance(
                timings.get("prompt_ms"),
                (int, float),
            )
            else None
        ),
        "generation_seconds": (
            timings.get("predicted_ms") / 1000
            if isinstance(
                timings.get("predicted_ms"),
                (int, float),
            )
            else None
        ),
        "prompt_tokens_per_second": (
            timings.get("prompt_per_second")
        ),
        "generation_tokens_per_second": (
            timings.get("predicted_per_second")
        ),
    }


def write_observation(
    *,
    condition: QuantizationCondition,
    task: dict[str, Any],
    repetition: int,
    server_pid: int,
    result: dict[str, Any],
) -> Path:
    task_id = task["task_id"]

    measurements = extract_measurements(
        result["response"]
    )

    payload = {
        "experiment": "012F-2",
        "task": {
            "task_id": task_id,
            "category": task["category"],
        },
        "provenance": {
            "runtime": "llama.cpp",
            "runtime_commit": RUNTIME_COMMIT,
            "runtime_version": RUNTIME_VERSION,
            "runtime_build": RUNTIME_BUILD,
            "model_id": condition.model_id,
            "quantization": condition.quantization,
            "artifact_bytes": (
                condition.expected_artifact_bytes
            ),
            "hardware_description": (
                HARDWARE_DESCRIPTION
            ),
            "repetition": repetition,
        },
        "configuration": {
            "threads": THREADS,
            "configured_context": (
                CONFIGURED_CONTEXT
            ),
            "parallel_slots": 1,
            "prompt_cache_enabled": False,
            "temperature": 0.0,
            "max_tokens": MAX_TOKENS,
        },
        "server_pid": server_pid,
        "measurements": {
            **measurements,
            "wall_time_seconds": (
                result["wall_time_seconds"]
            ),
        },
        "raw_response": result["response"],
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    path = RESULTS_DIR / (
        "012f2-"
        f"{condition.quantization.lower()}-"
        f"{task_id}-"
        f"run{repetition}.json"
    )

    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    return path


def validate_observation(
    path: Path,
    *,
    condition: QuantizationCondition,
    task: dict[str, Any],
    repetition: int,
) -> None:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    if payload["experiment"] != "012F-2":
        raise ValueError(
            f"{path}: wrong experiment identifier"
        )

    if payload["task"]["task_id"] != task["task_id"]:
        raise ValueError(
            f"{path}: wrong task identifier"
        )

    provenance = payload["provenance"]

    if (
        provenance["quantization"]
        != condition.quantization
    ):
        raise ValueError(
            f"{path}: wrong quantization"
        )

    if provenance["model_id"] != condition.model_id:
        raise ValueError(
            f"{path}: wrong model identifier"
        )

    if provenance["repetition"] != repetition:
        raise ValueError(
            f"{path}: wrong repetition"
        )

    configuration = payload["configuration"]

    expected_configuration = {
        "threads": THREADS,
        "configured_context": CONFIGURED_CONTEXT,
        "parallel_slots": 1,
        "prompt_cache_enabled": False,
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
    }

    if configuration != expected_configuration:
        raise ValueError(
            f"{path}: configuration drift detected"
        )

    measurements = payload["measurements"]

    if measurements["cached_prompt_tokens"] != 0:
        raise ValueError(
            f"{path}: prompt caching was observed"
        )

    prompt_tokens = measurements["prompt_tokens"]
    completion_tokens = measurements[
        "completion_tokens"
    ]
    total_tokens = measurements["total_tokens"]

    if not all(
        isinstance(value, int)
        for value in (
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )
    ):
        raise ValueError(
            f"{path}: missing token accounting"
        )

    if prompt_tokens + completion_tokens != total_tokens:
        raise ValueError(
            f"{path}: token accounting failed"
        )


def run_repetition(
    repetition: int,
) -> None:
    manifest = load_manifest()

    protocol_instruction = manifest[
        "response_protocol"
    ]["instruction"]

    tasks = manifest["tasks"]

    for condition in CONDITIONS:
        validate_artifact(condition)

        print(
            f"starting {condition.quantization} "
            f"for repetition {repetition}"
        )

        process, log_handle = start_server(condition)

        try:
            for index, task in enumerate(tasks, 1):
                print(
                    f"  task {index}/{len(tasks)}: "
                    f"{task['task_id']}"
                )

                result = request_completion(
                    condition=condition,
                    task=task,
                    protocol_instruction=(
                        protocol_instruction
                    ),
                )

                path = write_observation(
                    condition=condition,
                    task=task,
                    repetition=repetition,
                    server_pid=process.pid,
                    result=result,
                )

                validate_observation(
                    path,
                    condition=condition,
                    task=task,
                    repetition=repetition,
                )

        finally:
            stop_server(process)
            log_handle.close()

        print(
            f"completed {condition.quantization}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repetition",
        type=int,
        required=True,
        choices=(1, 2, 3),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not SERVER_BINARY.exists():
        raise FileNotFoundError(
            f"missing llama-server: {SERVER_BINARY}"
        )

    if not TASKS_PATH.exists():
        raise FileNotFoundError(
            f"missing frozen task manifest: {TASKS_PATH}"
        )

    ensure_port_is_free()

    run_repetition(args.repetition)

    print(
        "012F-2 repetition "
        f"{args.repetition} complete: "
        f"{len(CONDITIONS) * 10} validated observations"
    )


if __name__ == "__main__":
    main()