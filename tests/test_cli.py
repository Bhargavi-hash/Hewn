from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from hewn.cli import run_cli
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import (
    EchoModel,
    FinalResponse,
    Message,
    ModelError,
    ModelResponse,
)
from hewn.retrieval.semantic import FloatArray
from hewn.tools import ToolCall, ToolDefinition


class InvalidProtocolModel:
    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        del messages, tools

        raise ModelProtocolError(
            "Model response is not valid JSON",
            raw_response="not valid json",
        )

class FakeEmbeddingModel:
    def encode(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        return np.ones(
            (len(texts), 4),
            dtype=np.float32,
        )

def make_test_repository(root: Path) -> None:
    source = root / "sample.py"
    source.write_text(
        "def sample() -> str:\n"
        '    return "sample"\n',
        encoding="utf-8",
    )

class RepeatingToolModel:
    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        del messages, tools

        return ToolCall(
            name="list_directory",
            arguments={"path": "."},
        )

@dataclass
class StagnatingModel:
    calls: int = 0

    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        self.calls += 1

        if self.calls == 1:
            return ToolCall(
                name="run_check",
                arguments={"check": "tests"},
            )

        return FinalResponse(
            text="The tests failed. Please fix them."
        )
    
def test_cli_runs_request(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    make_test_repository(tmp_path)

    exit_code = run_cli(
        [
            "hello Hewn",
            "--workspace",
            str(tmp_path),
        ],
        model=EchoModel(),
        embedding_model=FakeEmbeddingModel(),
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Echo: hello Hewn" in captured.out
    assert "1 model calls" in captured.out
    assert "0 tool calls" in captured.out

def test_cli_reports_trace_when_agent_reaches_turn_limit(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    make_test_repository(tmp_path)
    exit_code = run_cli(
        [
            "Keep looking.",
            "--workspace",
            str(tmp_path),
            "--trace",
        ],
        model=RepeatingToolModel(),
        embedding_model=FakeEmbeddingModel(),
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Agent exceeded maximum turns: 20" in captured.out
    assert "20 model calls" in captured.out
    assert "20 tool calls" in captured.out
    assert "Trace:" in captured.out
    assert "list_directory" in captured.out

def test_cli_reports_trace_when_agent_stagnates(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    (tmp_path / "test_failure.py").write_text(
        "def test_failure() -> None:\n"
        "    assert False\n",
        encoding="utf-8",
    )
    make_test_repository(tmp_path)
    exit_code = run_cli(
        [
            "Fix the failing tests.",
            "--workspace",
            str(tmp_path),
            "--trace",
        ],
        model=StagnatingModel(),
        embedding_model=FakeEmbeddingModel(),
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Agent stagnated after 3 consecutive "
        "non-progressing turns"
        in captured.out
    )
    assert "4 model calls" in captured.out
    assert "1 tool calls" in captured.out
    assert "Trace:" in captured.out
    assert "completion_rejected" in captured.out
    assert "stagnation_detected" in captured.out

def test_cli_verify_requires_successful_check(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    make_test_repository(tmp_path)

    exit_code = run_cli(
        [
            "hello Hewn",
            "--workspace",
            str(tmp_path),
            "--verify",
            "--trace",
        ],
        model=EchoModel(),
        embedding_model=FakeEmbeddingModel(),
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "requires verification" in captured.out
    assert "completion_rejected" in captured.out


def test_cli_reports_model_protocol_error_without_traceback(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    make_test_repository(tmp_path)

    exit_code = run_cli(
        [
            "Fix the repository.",
            "--workspace",
            str(tmp_path),
        ],
        model=InvalidProtocolModel(),
        embedding_model=FakeEmbeddingModel(),
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Model protocol error: "
        "Model response is not valid JSON"
        in captured.out
    )
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err

def test_cli_preflights_llama_cpp_before_loading_embeddings(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    embedding_initialized = False

    def unavailable(self: LlamaCppModel) -> None:
        del self
        raise ModelError(
            "Could not reach llama.cpp: connection refused"
        )

    def fake_embedding_model(
        model_name: str,
    ) -> FakeEmbeddingModel:
        nonlocal embedding_initialized
        del model_name

        embedding_initialized = True
        return FakeEmbeddingModel()

    monkeypatch.setattr(
        LlamaCppModel,
        "check_available",
        unavailable,
    )
    monkeypatch.setattr(
        "hewn.cli.SentenceTransformerEmbeddingModel",
        fake_embedding_model,
    )

    exit_code = run_cli(
        [
            "Explain this repository.",
            "--workspace",
            str(tmp_path),
        ],
        model=LlamaCppModel(),
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Could not reach llama.cpp" in captured.out
    assert not embedding_initialized