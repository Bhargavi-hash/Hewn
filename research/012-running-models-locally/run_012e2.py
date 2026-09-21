from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
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

PROMPT_DIR = (
    REPO_ROOT
    / "research"
    / "012-running-models-locally"
    / "prompts"
    / "012e-consumed-context"
)

RESULTS_DIR = (
    REPO_ROOT
    / "research"
    / "012-running-models-locally"
    / "results"
)

LOG_DIR = RESULTS_DIR / "012e-server-logs"

MODEL_ID = (
    "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:"
    "Q4_K_M"
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

TARGETS = (
    256,
    512,
    1024,
    2048,
    4096,
)

REPETITIONS = 5

THREADS = 4
CONTEXT = 8192
MAX_TOKENS = 128
PORT = 8080

BASE_URL = f"http://127.0.0.1:{PORT}"

REQUEST_TIMEOUT_SECONDS = 300.0
STARTUP_TIMEOUT_SECONDS = 120.0


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
            "Stop it before starting 012E-2."
        )


def start_server(
    *,
    target: int,
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
        / f"ctx-{target}.log"
    )

    log_file = log_path.open("wb")

    command = [
        str(SERVER_BINARY),
        "-hf",
        MODEL_ID,
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
        f"Starting fresh server for "
        f"{target} prompt tokens"
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
    target: int,
    repetition: int,
    server_pid: int,
) -> Path:
    prompt_path = (
        PROMPT_DIR
        / f"prompt-{target}.txt"
    )

    prompt = prompt_path.read_text(
        encoding="utf-8"
    )

    output_path = (
        RESULTS_DIR
        / (
            f"012e-consumed-{target}-"
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
        MODEL_ID,
        "--quantization",
        "Q4_K_M",
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
    expected_prompt_tokens: int,
) -> None:
    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

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
        != expected_prompt_tokens
    ):
        raise RuntimeError(
            f"{path}: expected "
            f"{expected_prompt_tokens} prompt tokens, "
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
        != expected_prompt_tokens
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

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for target in TARGETS:
        prompt_path = (
            PROMPT_DIR
            / f"prompt-{target}.txt"
        )

        if not prompt_path.exists():
            raise SystemExit(
                f"missing frozen prompt: "
                f"{prompt_path}"
            )

    produced: list[Path] = []

    for target in TARGETS:
        process, log_file = start_server(
            target=target
        )

        try:
            for repetition in range(
                1,
                REPETITIONS + 1,
            ):
                output_path = run_measurement(
                    target=target,
                    repetition=repetition,
                    server_pid=process.pid,
                )

                validate_result(
                    path=output_path,
                    expected_prompt_tokens=target,
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
            f"completed {target}-token condition"
        )

    print()
    print(
        f"012E-2 complete: "
        f"{len(produced)} validated runs"
    )

    print(
        "Every condition used a fresh "
        "llama-server process."
    )


if __name__ == "__main__":
    main()