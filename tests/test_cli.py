from pathlib import Path

from _pytest.capture import CaptureFixture

from hewn.cli import run_cli
from hewn.models import EchoModel


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