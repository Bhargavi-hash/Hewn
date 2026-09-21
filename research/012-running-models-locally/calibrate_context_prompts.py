from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


BASE_URL = "http://127.0.0.1:8080"

CORPUS_PATH = Path(
    "research/012-running-models-locally/"
    "prompts/012e-consumed-context/corpus.txt"
)

OUTPUT_DIR = Path(
    "research/012-running-models-locally/"
    "prompts/012e-consumed-context"
)

MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K_M"

TARGETS = (
    256,
    512,
    1024,
    2048,
    4096,
)

TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class CalibrationResult:
    target_tokens: int
    actual_prompt_tokens: int
    raw_content_tokens: int
    chat_template_overhead_tokens: int
    character_count: int
    filename: str
    absolute_error: int


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("expected JSON object")

    return {
        str(key): item
        for key, item in value.items()
    }


def _post_json(
    *,
    endpoint: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:
            response_body = response.read()

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"llama.cpp request failed: "
            f"HTTP {exc.code} {exc.reason}\n"
            f"endpoint: {endpoint}\n"
            f"response: {error_body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"llama.cpp request failed: {exc}"
        ) from exc

    parsed = json.loads(response_body)

    return _mapping(parsed)


def count_raw_tokens(text: str) -> int:
    response = _post_json(
        endpoint="/tokenize",
        payload={
            "content": text,
        },
    )

    tokens = response.get("tokens")

    if not isinstance(tokens, list):
        raise RuntimeError(
            "llama.cpp /tokenize response did not contain "
            "a token list"
        )

    return len(tokens)


def measure_chat_prompt_tokens(prompt: str) -> int:
    response = _post_json(
        endpoint="/v1/chat/completions",
        payload={
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.0,
            "max_tokens": 1,
        },
    )

    usage = _mapping(response.get("usage"))

    prompt_tokens = usage.get("prompt_tokens")

    if (
        isinstance(prompt_tokens, bool)
        or not isinstance(prompt_tokens, int)
    ):
        raise RuntimeError(
            "llama.cpp response did not contain integer "
            "'usage.prompt_tokens'"
        )

    return prompt_tokens


def measure_chat_template_overhead() -> int:
    probe = "hello world"

    raw_tokens = count_raw_tokens(probe)
    prompt_tokens = measure_chat_prompt_tokens(probe)

    overhead = prompt_tokens - raw_tokens

    if overhead < 0:
        raise RuntimeError(
            "chat prompt token count was smaller than raw "
            "content token count"
        )

    return overhead


def find_prefix_for_raw_target(
    *,
    corpus: str,
    target_raw_tokens: int,
) -> tuple[str, int]:
    low = 1
    high = len(corpus)

    best_prefix = corpus[:1]
    best_tokens = count_raw_tokens(best_prefix)
    best_error = abs(
        best_tokens - target_raw_tokens
    )

    while low <= high:
        middle = (low + high) // 2
        candidate = corpus[:middle]

        actual_tokens = count_raw_tokens(candidate)

        error = abs(
            actual_tokens - target_raw_tokens
        )

        if (
            error < best_error
            or (
                error == best_error
                and actual_tokens < best_tokens
            )
        ):
            best_prefix = candidate
            best_tokens = actual_tokens
            best_error = error

        if actual_tokens < target_raw_tokens:
            low = middle + 1
        elif actual_tokens > target_raw_tokens:
            high = middle - 1
        else:
            return candidate, actual_tokens

    center = len(best_prefix)

    neighborhood_start = max(
        1,
        center - 32,
    )

    neighborhood_end = min(
        len(corpus),
        center + 32,
    )

    for character_count in range(
        neighborhood_start,
        neighborhood_end + 1,
    ):
        candidate = corpus[:character_count]

        actual_tokens = count_raw_tokens(candidate)

        error = abs(
            actual_tokens - target_raw_tokens
        )

        if (
            error < best_error
            or (
                error == best_error
                and actual_tokens < best_tokens
            )
        ):
            best_prefix = candidate
            best_tokens = actual_tokens
            best_error = error

        if actual_tokens == target_raw_tokens:
            break

    return best_prefix, best_tokens


def calibrate_target(
    *,
    corpus: str,
    target_tokens: int,
    initial_overhead: int,
) -> CalibrationResult:
    desired_raw_tokens = max(
        1,
        target_tokens - initial_overhead,
    )

    prompt, raw_tokens = find_prefix_for_raw_target(
        corpus=corpus,
        target_raw_tokens=desired_raw_tokens,
    )

    actual_prompt_tokens = measure_chat_prompt_tokens(
        prompt
    )

    # Usually the initial overhead estimate is already exact.
    # If the final chat-template count differs from the target,
    # adjust the raw target deterministically and recalibrate.
    attempts = 0

    while (
        actual_prompt_tokens != target_tokens
        and attempts < 8
    ):
        difference = (
            target_tokens - actual_prompt_tokens
        )

        desired_raw_tokens = max(
            1,
            raw_tokens + difference,
        )

        prompt, raw_tokens = find_prefix_for_raw_target(
            corpus=corpus,
            target_raw_tokens=desired_raw_tokens,
        )

        actual_prompt_tokens = (
            measure_chat_prompt_tokens(prompt)
        )

        attempts += 1

    filename = f"prompt-{target_tokens}.txt"

    return CalibrationResult(
        target_tokens=target_tokens,
        actual_prompt_tokens=actual_prompt_tokens,
        raw_content_tokens=raw_tokens,
        chat_template_overhead_tokens=(
            actual_prompt_tokens - raw_tokens
        ),
        character_count=len(prompt),
        filename=filename,
        absolute_error=abs(
            actual_prompt_tokens - target_tokens
        ),
    )


def main() -> None:
    if not CORPUS_PATH.exists():
        raise SystemExit(
            f"corpus does not exist: {CORPUS_PATH}"
        )

    corpus = CORPUS_PATH.read_text(
        encoding="utf-8"
    )

    if not corpus:
        raise SystemExit("corpus is empty")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Calibrating consumed-context workloads"
    )
    print(
        f"corpus characters: {len(corpus)}"
    )
    print()

    overhead = measure_chat_template_overhead()

    print(
        "initial chat-template overhead: "
        f"{overhead} tokens"
    )
    print()

    results: list[CalibrationResult] = []

    prompts: dict[int, str] = {}

    for target in TARGETS:
        print(
            f"target: {target} prompt tokens"
        )

        result = calibrate_target(
            corpus=corpus,
            target_tokens=target,
            initial_overhead=overhead,
        )

        desired_raw_tokens = max(
            1,
            target - overhead,
        )

        prompt, _ = find_prefix_for_raw_target(
            corpus=corpus,
            target_raw_tokens=desired_raw_tokens,
        )

        # Reconstruct the exact calibrated prompt if the
        # first overhead estimate required adjustment.
        actual = measure_chat_prompt_tokens(prompt)

        attempts = 0

        while (
            actual != result.actual_prompt_tokens
            and attempts < 8
        ):
            difference = (
                result.actual_prompt_tokens - actual
            )

            raw = count_raw_tokens(prompt)

            prompt, _ = find_prefix_for_raw_target(
                corpus=corpus,
                target_raw_tokens=max(
                    1,
                    raw + difference,
                ),
            )

            actual = measure_chat_prompt_tokens(
                prompt
            )

            attempts += 1

        output_path = (
            OUTPUT_DIR / result.filename
        )

        output_path.write_text(
            prompt,
            encoding="utf-8",
        )

        # Read back and verify the exact persisted file.
        persisted_prompt = output_path.read_text(
            encoding="utf-8"
        )

        persisted_raw_tokens = count_raw_tokens(
            persisted_prompt
        )

        persisted_prompt_tokens = (
            measure_chat_prompt_tokens(
                persisted_prompt
            )
        )

        persisted_result = CalibrationResult(
            target_tokens=target,
            actual_prompt_tokens=(
                persisted_prompt_tokens
            ),
            raw_content_tokens=(
                persisted_raw_tokens
            ),
            chat_template_overhead_tokens=(
                persisted_prompt_tokens
                - persisted_raw_tokens
            ),
            character_count=len(
                persisted_prompt
            ),
            filename=result.filename,
            absolute_error=abs(
                persisted_prompt_tokens - target
            ),
        )

        results.append(persisted_result)
        prompts[target] = persisted_prompt

        print(
            "  "
            f"actual="
            f"{persisted_prompt_tokens} "
            f"raw="
            f"{persisted_raw_tokens} "
            f"overhead="
            f"{persisted_result.chat_template_overhead_tokens} "
            f"characters="
            f"{len(persisted_prompt)} "
            f"error="
            f"{persisted_result.absolute_error}"
        )

    prefix_checks: list[dict[str, Any]] = []

    for smaller, larger in zip(
        TARGETS,
        TARGETS[1:],
    ):
        is_prefix = prompts[larger].startswith(
            prompts[smaller]
        )

        prefix_checks.append(
            {
                "smaller_target": smaller,
                "larger_target": larger,
                "is_prefix": is_prefix,
            }
        )

    manifest = {
        "experiment": "012E-2",
        "purpose": "consumed context scaling",
        "calibration_method": (
            "raw tokenization followed by authoritative "
            "chat-completion verification"
        ),
        "tokenizer_endpoint": (
            f"{BASE_URL}/tokenize"
        ),
        "verification_endpoint": (
            f"{BASE_URL}/v1/chat/completions"
        ),
        "model_id": MODEL_ID,
        "configured_context": 8192,
        "threads": 4,
        "parallel_slots": 1,
        "prompt_cache_enabled": False,
        "temperature": 0.0,
        "verification_max_tokens": 1,
        "source_corpus": str(CORPUS_PATH),
        "initial_chat_template_overhead_tokens": (
            overhead
        ),
        "targets": [
            asdict(result)
            for result in results
        ],
        "prefix_checks": prefix_checks,
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(
        f"{'target':>8} "
        f"{'actual':>8} "
        f"{'raw':>8} "
        f"{'overhead':>10} "
        f"{'error':>8} "
        f"{'chars':>8}"
    )

    for result in results:
        print(
            f"{result.target_tokens:8d} "
            f"{result.actual_prompt_tokens:8d} "
            f"{result.raw_content_tokens:8d} "
            f"{result.chat_template_overhead_tokens:10d} "
            f"{result.absolute_error:8d} "
            f"{result.character_count:8d}"
        )

    print()
    print("Prefix checks:")

    all_prefixes = True

    for check in prefix_checks:
        status = (
            "PREFIX"
            if check["is_prefix"]
            else "NOT PREFIX"
        )

        print(
            f"{check['smaller_target']:4d} "
            f"-> "
            f"{check['larger_target']:4d}: "
            f"{status}"
        )

        all_prefixes &= bool(
            check["is_prefix"]
        )

    if not all_prefixes:
        raise SystemExit(
            "calibrated prompts are not nested prefixes"
        )

    if any(
        result.absolute_error > 1
        for result in results
    ):
        raise SystemExit(
            "one or more calibrated workloads are "
            "more than one token from their targets"
        )

    print()
    print("Calibration validation: PASS")


if __name__ == "__main__":
    main()