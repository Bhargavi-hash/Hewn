from __future__ import annotations

from typing import Any

import pytest

from . import measure as measure_module
from .measure import (
    InferenceConfiguration,
    Provenance,
    normalize_response,
)
from .process_memory import ProcessMemory


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


def _provenance() -> Provenance:
    return Provenance(
        runtime="llama.cpp",
        runtime_commit="test-commit",
        runtime_version="test-version",
        runtime_build="test-build",
        model_id="test-model",
        quantization="Q4_K_M",
        hardware_description="test-hardware",
    )


def _configuration() -> InferenceConfiguration:
    return InferenceConfiguration(
        base_url="http://127.0.0.1:8080",
        threads=4,
        configured_context=4096,
        prompt_cache_enabled=False,
        temperature=0.0,
        max_tokens=64,
    )


def _memory(
    *,
    vm_peak_kb: int,
    vm_size_kb: int,
    vm_hwm_kb: int,
    vm_rss_kb: int,
) -> ProcessMemory:
    return ProcessMemory(
        vm_peak_kb=vm_peak_kb,
        vm_size_kb=vm_size_kb,
        vm_hwm_kb=vm_hwm_kb,
        vm_rss_kb=vm_rss_kb,
        rss_anon_kb=900,
        rss_file_kb=500,
        vm_data_kb=800,
        vm_swap_kb=0,
    )


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


def test_measure_records_explicit_process_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _memory(
        vm_peak_kb=2000,
        vm_size_kb=1800,
        vm_hwm_kb=1500,
        vm_rss_kb=1400,
    )
    after = _memory(
        vm_peak_kb=2200,
        vm_size_kb=1900,
        vm_hwm_kb=1700,
        vm_rss_kb=1500,
    )

    readings = iter((before, after))

    def fake_read_process_memory(pid: int) -> ProcessMemory:
        assert pid == 12345
        return next(readings)

    def fake_request_completion(
        *,
        configuration: InferenceConfiguration,
        model_id: str,
        prompt: str,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], float]:
        assert configuration == _configuration()
        assert configuration.prompt_cache_enabled is False
        assert model_id == "test-model"
        assert prompt == "test prompt"
        assert timeout_seconds == pytest.approx(120.0)

        return _response(), 2.1

    monkeypatch.setattr(
        measure_module,
        "read_process_memory",
        fake_read_process_memory,
    )
    monkeypatch.setattr(
        measure_module,
        "request_completion",
        fake_request_completion,
    )

    run = measure_module.measure(
        provenance=_provenance(),
        configuration=_configuration(),
        prompt="test prompt",
        server_pid=12345,
    )

    assert run.memory is not None
    assert run.memory.server_pid == 12345
    assert run.memory.before_request == before
    assert run.memory.after_request == after

    assert run.configuration.prompt_cache_enabled is False

    assert run.measurements.prompt_tokens == 47
    assert run.measurements.generated_tokens == 17
    assert run.measurements.wall_time_seconds == pytest.approx(2.1)

    assert run.accounting.all_observed_valid is True


def test_measure_without_server_pid_does_not_read_process_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_memory_is_read(pid: int) -> ProcessMemory:
        raise AssertionError(
            f"read_process_memory unexpectedly called for PID {pid}"
        )

    def fake_request_completion(
        *,
        configuration: InferenceConfiguration,
        model_id: str,
        prompt: str,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], float]:
        assert configuration == _configuration()
        assert model_id == "test-model"
        assert prompt == "test prompt"
        assert timeout_seconds == pytest.approx(120.0)

        return _response(), 2.1

    monkeypatch.setattr(
        measure_module,
        "read_process_memory",
        fail_if_memory_is_read,
    )
    monkeypatch.setattr(
        measure_module,
        "request_completion",
        fake_request_completion,
    )

    run = measure_module.measure(
        provenance=_provenance(),
        configuration=_configuration(),
        prompt="test prompt",
    )

    assert run.memory is None
    assert run.configuration.prompt_cache_enabled is False
    assert run.accounting.all_observed_valid is True