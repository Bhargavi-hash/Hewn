from pathlib import Path

from _pytest.capture import CaptureFixture

from hewn.cli import run_cli
from hewn.models import EchoModel, Message, ModelResponse
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