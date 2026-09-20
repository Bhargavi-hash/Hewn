from __future__ import annotations

from typing import Any

import pytest

from .measure import normalize_response


def _response() -> dict[str, Any]:
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "example",
                },
            }
        ],
        "usage": {
            "completion_tokens": 17,
            "prompt_tokens": 47,
            "total_tokens": 64,
            "prompt_tokens_details": {
                "cached_tokens": 5,
            },
        },
        "timings": {
            "cache_n": 5,
            "prompt_n": 42,
            "prompt_ms": 714.381,
            "prompt_per_second": 58.79215712623937,
            "predicted_n": 17,
            "predicted_ms": 1201.587,
            "predicted_per_second": 13.315723289283257,
        },
    }


def test_normalizes_observed_llama_cpp_response() -> None:
    measurements, accounting = normalize_response(
        response=_response(),
        wall_time_seconds=2.1,
    )

    assert measurements.prompt_tokens == 47
    assert measurements.completion_tokens == 17
    assert measurements.total_tokens == 64

    assert measurements.cached_prompt_tokens == 5
    assert measurements.prompt_evaluated_tokens == 42
    assert measurements.generated_tokens == 17

    assert measurements.prompt_seconds == pytest.approx(0.714381)
    assert measurements.generation_seconds == pytest.approx(1.201587)

    assert measurements.prompt_tokens_per_second == pytest.approx(
        58.79215712623937
    )
    assert measurements.generation_tokens_per_second == pytest.approx(
        13.315723289283257
    )

    assert measurements.wall_time_seconds == pytest.approx(2.1)
    assert measurements.finish_reason == "stop"

    assert accounting.total_token_accounting is True
    assert accounting.prompt_cache_accounting is True
    assert accounting.generation_token_accounting is True
    assert accounting.all_observed_valid is True


def test_missing_measurements_remain_missing() -> None:
    measurements, accounting = normalize_response(
        response={
            "choices": [],
        },
        wall_time_seconds=1.0,
    )

    assert measurements.prompt_tokens is None
    assert measurements.completion_tokens is None
    assert measurements.cached_prompt_tokens is None
    assert measurements.prompt_evaluated_tokens is None
    assert measurements.prompt_seconds is None
    assert measurements.generation_seconds is None
    assert measurements.finish_reason is None

    assert accounting.total_token_accounting is None
    assert accounting.prompt_cache_accounting is None
    assert accounting.generation_token_accounting is None

    assert accounting.all_observed_valid is True


def test_detects_total_token_accounting_failure() -> None:
    response = _response()
    response["usage"]["total_tokens"] = 999

    _, accounting = normalize_response(
        response=response,
        wall_time_seconds=1.0,
    )

    assert accounting.total_token_accounting is False
    assert accounting.all_observed_valid is False


def test_detects_prompt_cache_accounting_failure() -> None:
    response = _response()
    response["timings"]["prompt_n"] = 41

    _, accounting = normalize_response(
        response=response,
        wall_time_seconds=1.0,
    )

    assert accounting.prompt_cache_accounting is False
    assert accounting.all_observed_valid is False


def test_detects_generation_token_accounting_failure() -> None:
    response = _response()
    response["timings"]["predicted_n"] = 16

    _, accounting = normalize_response(
        response=response,
        wall_time_seconds=1.0,
    )

    assert accounting.generation_token_accounting is False
    assert accounting.all_observed_valid is False


def test_protocol_booleans_are_not_accepted_as_numeric_measurements() -> None:
    response = _response()
    response["usage"]["prompt_tokens"] = True

    measurements, accounting = normalize_response(
        response=response,
        wall_time_seconds=1.0,
    )

    assert measurements.prompt_tokens is None
    assert accounting.total_token_accounting is None