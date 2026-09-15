from pathlib import Path

from _pytest.capture import CaptureFixture

from hewn.cli import main


def test_cli_runs_request(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "hello Hewn",
            "--workspace",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "Echo: hello Hewn\n"