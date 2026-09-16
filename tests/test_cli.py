from dataclasses import dataclass
from pathlib import Path

from _pytest.capture import CaptureFixture

from hewn.cli import run_cli
from hewn.models import EchoModel, FinalResponse, Message, ModelResponse
from hewn.tools import ToolCall, ToolDefinition


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
    exit_code = run_cli(
        [
            "hello Hewn",
            "--workspace",
            str(tmp_path),
        ],
        model=EchoModel(),
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
    exit_code = run_cli(
        [
            "Keep looking.",
            "--workspace",
            str(tmp_path),
            "--trace",
        ],
        model=RepeatingToolModel(),
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

    exit_code = run_cli(
        [
            "Fix the failing tests.",
            "--workspace",
            str(tmp_path),
            "--trace",
        ],
        model=StagnatingModel(),
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