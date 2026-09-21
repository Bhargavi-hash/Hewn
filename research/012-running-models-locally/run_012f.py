from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

REPO_ROOT = Path(__file__).resolve().parents[2]

LLAMA_CPP_ROOT = Path.home() / "Documents" / "llama.cpp"

SERVER_BINARY = (
    LLAMA_CPP_ROOT
    / "build"
    / "bin"
    / "llama-server"
)

HARNESS_MODULE = (
    "research.012-running-models-locally."
    "harness.measure"
)

PROMPT_PATH = (
    REPO_ROOT
    / "research"
    / "012-running-models-locally"
    / "prompts"
    / "012e-consumed-context"
    / "prompt-1024.txt"
)

RESULTS_DIR = (
    REPO_ROOT
    / "research"
    / "012-running-models-locally"
    / "results"
)

LOG_DIR = RESULTS_DIR / "012f-server-logs"

HF_CACHE_ROOT = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--Qwen--Qwen2.5-Coder-1.5B-Instruct-GGUF"
)

HF_SNAPSHOT = (
    "f86cb2c1fa58255f8052cc32aeede1b7482d4361"
)

HF_REPOSITORY = (
    "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
)

RUNTIME_COMMIT = (
    "930e2fa5995789efbf249a8bf61325bb626e417b"
)

RUNTIME_VERSION = "0.4.1-dev"

RUNTIME_BUILD = (
    "build 10991, commit 930e2fa59"
)

HARDWARE_DESCRIPTION = (
    "Intel Core i5-10210U, "
    "4 physical cores / 8 logical CPUs, "
    "~7.6 GiB RAM, no NVIDIA GPU"
)

REPETITIONS = 5

EXPECTED_PROMPT_TOKENS = 1024

THREADS = 4
CONTEXT = 8192
MAX_TOKENS = 128
PORT = 8080

BASE_URL = f"http://127.0.0.1:{PORT}"

REQUEST_TIMEOUT_SECONDS = 300.0
STARTUP_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class QuantizationCondition:
    quantization: str
    filename: str
    blob_hash: str
    expected_artifact_bytes: int

    @property
    def model_id(self) -> str:
        return (
            f"{HF_REPOSITORY}:"
            f"{self.quantization}"
        )

    @property
    def snapshot_path(self) -> Path:
        return (
            HF_CACHE_ROOT
            / "snapshots"
            / HF_SNAPSHOT
            / self.filename
        )

    @property
    def blob_path(self) -> Path:
        return (
            HF_CACHE_ROOT
            / "blobs"
            / self.blob_hash
        )


CONDITIONS = (
    QuantizationCondition(
        quantization="Q3_K_M",
        filename=(
            "qwen2.5-coder-1.5b-instruct-"
            "q3_k_m.gguf"
        ),
        blob_hash=(
            "d281a3a0010df03c8a0e3ffebd7f9444"
            "a95244fb518f132c5475e4b48d9adb5e"
        ),
        expected_artifact_bytes=924_456_000,
    ),
    QuantizationCondition(
        quantization="Q4_K_M",
        filename=(
            "qwen2.5-coder-1.5b-instruct-"
            "q4_k_m.gguf"
        ),
        blob_hash=(
            "cc324af070c2ecbfd324a30884d2f951"
            "a7ff756aba85cb811a6ec436933bb046"
        ),
        expected_artifact_bytes=1_117_320_768,
    ),
    QuantizationCondition(
        quantization="Q5_K_M",
        filename=(
            "qwen2.5-coder-1.5b-instruct-"
            "q5_k_m.gguf"
        ),
        blob_hash=(
            "f15d02e8e51a5c6f9448b972819acfa"
            "66aee4d8bb7d881a8b8ba3d90da08ef09"
        ),
        expected_artifact_bytes=1_285_494_336,
    ),
    QuantizationCondition(
        quantization="Q6_K",
        filename=(
            "qwen2.5-coder-1.5b-instruct-"
            "q6_k.gguf"
        ),
        blob_hash=(
            "9b05dce8089197c866b9f76e1db45de"
            "8617cda98d9d06059958cb8ad32c56dfa"
        ),
        expected_artifact_bytes=1_464_178_752,
    ),
    QuantizationCondition(
        quantization="Q8_0",
        filename=(
            "qwen2.5-coder-1.5b-instruct-"
            "q8_0.gguf"
        ),
        blob_hash=(
            "507de59046601282ba768a9789900e6cc"
            "f60ed93ddf346730b7c68eb0715bc47"
        ),
        expected_artifact_bytes=1_894_532_160,
    ),
)


def server_is_ready() -> bool:
    try:
        with urllib.request.urlopen(
            f"{BASE_URL}/health",
            timeout=2.0,
        ) as response:
            return bool(response.status == 200)
    except (
        urllib.error.URLError,
        TimeoutError,
    ):
        return False


def wait_for_server(
    process: subprocess.Popen[bytes],
) -> None:
    deadline = (
        time.monotonic()
        + STARTUP_TIMEOUT_SECONDS
    )

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "llama-server exited before becoming ready"
            )

        if server_is_ready():
            return

        time.sleep(0.5)

    raise RuntimeError(
        "timed out waiting for llama-server"
    )


def ensure_port_is_free() -> None:
    if server_is_ready():
        raise RuntimeError(
            f"{BASE_URL} already has a responding server. "
            "Stop it before starting 012F."
        )


def validate_artifact(
    condition: QuantizationCondition,
) -> None:
    snapshot_path = condition.snapshot_path
    blob_path = condition.blob_path

    if not snapshot_path.exists():
        raise RuntimeError(
            "missing cached snapshot artifact for "
            f"{condition.quantization}: "
            f"{snapshot_path}"
        )

    if not snapshot_path.is_symlink():
        raise RuntimeError(
            "expected Hugging Face snapshot artifact "
            f"to be a symlink: {snapshot_path}"
        )

    resolved_path = snapshot_path.resolve()

    if resolved_path != blob_path.resolve():
        raise RuntimeError(
            f"{condition.quantization}: snapshot resolves "
            "to unexpected blob"
        )

    observed_bytes = blob_path.stat().st_size

    if observed_bytes != condition.expected_artifact_bytes:
        raise RuntimeError(
            f"{condition.quantization}: expected artifact "
            f"size {condition.expected_artifact_bytes}, "
            f"observed {observed_bytes}"
        )


def start_server(
    *,
    condition: QuantizationCondition,
) -> tuple[
    subprocess.Popen[bytes],
    BinaryIO,
]:
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = (
        LOG_DIR
        / f"{condition.quantization.lower()}.log"
    )

    log_file = log_path.open("wb")

    command = [
        str(SERVER_BINARY),
        "-hf",
        condition.model_id,
        "-t",
        str(THREADS),
        "-c",
        str(CONTEXT),
        "--parallel",
        "1",
        "--no-cache-prompt",
        "--metrics",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ]

    print()
    print(
        "Starting fresh server for "
        f"{condition.quantization}"
    )
    print(
        f"artifact bytes: "
        f"{condition.expected_artifact_bytes}"
    )
    print(
        f"server log: {log_path}"
    )

    process = subprocess.Popen(
        command,
        cwd=LLAMA_CPP_ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    try:
        wait_for_server(process)
    except Exception:
        log_file.close()
        raise

    print(
        f"server PID: {process.pid}"
    )

    return process, log_file


def stop_server(
    process: subprocess.Popen[bytes],
    log_file: BinaryIO,
) -> None:
    if process.poll() is None:
        try:
            os.killpg(
                process.pid,
                signal.SIGTERM,
            )

            process.wait(
                timeout=15.0,
            )

        except subprocess.TimeoutExpired:
            os.killpg(
                process.pid,
                signal.SIGKILL,
            )

            process.wait(
                timeout=5.0,
            )

    log_file.close()


def run_measurement(
    *,
    condition: QuantizationCondition,
    repetition: int,
    server_pid: int,
    prompt: str,
) -> Path:
    output_path = (
        RESULTS_DIR
        / (
            "012f-quantization-"
            f"{condition.quantization.lower()}-"
            f"run{repetition}.json"
        )
    )

    command = [
        sys.executable,
        "-m",
        HARNESS_MODULE,
        "--base-url",
        BASE_URL,
        "--runtime-commit",
        RUNTIME_COMMIT,
        "--runtime-version",
        RUNTIME_VERSION,
        "--runtime-build",
        RUNTIME_BUILD,
        "--model-id",
        condition.model_id,
        "--quantization",
        condition.quantization,
        "--hardware",
        HARDWARE_DESCRIPTION,
        "--threads",
        str(THREADS),
        "--context",
        str(CONTEXT),
        "--prompt-cache",
        "disabled",
        "--temperature",
        "0",
        "--max-tokens",
        str(MAX_TOKENS),
        "--prompt",
        prompt,
        "--timeout",
        str(REQUEST_TIMEOUT_SECONDS),
        "--server-pid",
        str(server_pid),
        "--output",
        str(output_path),
    ]

    print(
        f"  run {repetition}/{REPETITIONS}"
    )

    subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
    )

    return output_path


def validate_result(
    *,
    path: Path,
    condition: QuantizationCondition,
) -> None:
    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    provenance = payload[
        "provenance"
    ]

    configuration = payload[
        "configuration"
    ]

    measurements = payload[
        "measurements"
    ]

    accounting = payload[
        "accounting"
    ]

    if (
        provenance["model_id"]
        != condition.model_id
    ):
        raise RuntimeError(
            f"{path}: unexpected model ID"
        )

    if (
        provenance["quantization"]
        != condition.quantization
    ):
        raise RuntimeError(
            f"{path}: unexpected quantization"
        )

    if (
        configuration[
            "configured_context"
        ]
        != CONTEXT
    ):
        raise RuntimeError(
            f"{path}: unexpected configured context"
        )

    if (
        configuration[
            "threads"
        ]
        != THREADS
    ):
        raise RuntimeError(
            f"{path}: unexpected thread count"
        )

    if (
        configuration[
            "prompt_cache_enabled"
        ]
        is not False
    ):
        raise RuntimeError(
            f"{path}: prompt cache not recorded "
            "as disabled"
        )

    if (
        measurements[
            "prompt_tokens"
        ]
        != EXPECTED_PROMPT_TOKENS
    ):
        raise RuntimeError(
            f"{path}: expected "
            f"{EXPECTED_PROMPT_TOKENS} prompt tokens, "
            f"observed "
            f"{measurements['prompt_tokens']}"
        )

    if (
        measurements[
            "cached_prompt_tokens"
        ]
        != 0
    ):
        raise RuntimeError(
            f"{path}: observed cached prompt tokens"
        )

    if (
        measurements[
            "prompt_evaluated_tokens"
        ]
        != EXPECTED_PROMPT_TOKENS
    ):
        raise RuntimeError(
            f"{path}: prompt was not fully evaluated"
        )

    accounting_checks = (
        "total_token_accounting",
        "prompt_cache_accounting",
        "generation_token_accounting",
    )

    for check in accounting_checks:
        if accounting.get(check) is not True:
            raise RuntimeError(
                f"{path}: {check} was not true"
            )

    memory = payload.get(
        "memory"
    )

    if memory is None:
        raise RuntimeError(
            f"{path}: memory measurements missing"
        )

    if (
        memory.get("server_pid")
        is None
    ):
        raise RuntimeError(
            f"{path}: server PID missing from "
            "memory measurements"
        )

    if (
        memory.get("before_request")
        is None
    ):
        raise RuntimeError(
            f"{path}: before-request memory "
            "measurement missing"
        )

    if (
        memory.get("after_request")
        is None
    ):
        raise RuntimeError(
            f"{path}: after-request memory "
            "measurement missing"
        )


def main() -> None:
    ensure_port_is_free()

    if not SERVER_BINARY.exists():
        raise SystemExit(
            f"llama-server not found: "
            f"{SERVER_BINARY}"
        )

    if not PROMPT_PATH.exists():
        raise SystemExit(
            f"missing frozen prompt: "
            f"{PROMPT_PATH}"
        )

    for condition in CONDITIONS:
        validate_artifact(
            condition
        )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    prompt = PROMPT_PATH.read_text(
        encoding="utf-8"
    )

    produced: list[Path] = []

    for condition in CONDITIONS:
        process, log_file = start_server(
            condition=condition
        )

        try:
            for repetition in range(
                1,
                REPETITIONS + 1,
            ):
                output_path = run_measurement(
                    condition=condition,
                    repetition=repetition,
                    server_pid=process.pid,
                    prompt=prompt,
                )

                validate_result(
                    path=output_path,
                    condition=condition,
                )

                produced.append(
                    output_path
                )

        finally:
            stop_server(
                process,
                log_file,
            )

        print(
            "completed "
            f"{condition.quantization} condition"
        )

    expected_runs = (
        len(CONDITIONS)
        * REPETITIONS
    )

    if len(produced) != expected_runs:
        raise RuntimeError(
            f"expected {expected_runs} runs, "
            f"produced {len(produced)}"
        )

    print()
    print(
        "012F-1 complete: "
        f"{len(produced)} validated runs"
    )

    print(
        "Every quantization condition used a fresh "
        "llama-server process."
    )


if __name__ == "__main__":
    main()