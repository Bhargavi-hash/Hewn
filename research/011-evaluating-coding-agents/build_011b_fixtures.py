from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = MODULE_ROOT / "fixtures-011b"


TASKS: tuple[dict[str, Any], ...] = (
    {
        "task_id": "stability-001",
        "request": (
            'Change greeting() so it returns "hi" instead of "hello". '
            "Preserve all other behavior."
        ),
        "expected_changed_files": ["src/sample/greeting.py"],
        "files": {
            "pyproject.toml": """
[project]
name = "hewn-stability-001"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
            "src/sample/__init__.py": "",
            "src/sample/greeting.py": """
def greeting() -> str:
    return "hello"


def stable_identifier(name: str) -> str:
    return f"user:{name}"
""",
            "tests/test_greeting.py": """
from sample.greeting import stable_identifier


def test_stable_identifier() -> None:
    assert stable_identifier("Alice") == "user:Alice"
""",
        },
    },
    {
        "task_id": "stability-002",
        "request": (
            "Increase the default request retry count from 2 to 4. "
            "Preserve request_policy() as the consumer of the shared setting."
        ),
        "expected_changed_files": ["src/sample/settings.py"],
        "files": {
            "pyproject.toml": """
[project]
name = "hewn-stability-002"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
            "src/sample/__init__.py": "",
            "src/sample/settings.py": """
DEFAULT_RETRIES = 2
""",
            "src/sample/client.py": """
from sample.settings import DEFAULT_RETRIES


def request_policy() -> int:
    return DEFAULT_RETRIES


def stable_identifier(name: str) -> str:
    return f"user:{name}"
""",
            "tests/test_client.py": """
from sample.client import stable_identifier


def test_stable_identifier() -> None:
    assert stable_identifier("Alice") == "user:Alice"
""",
        },
    },
    {
        "task_id": "stability-003",
        "request": (
            "Normalize names by stripping surrounding whitespace and "
            "converting non-empty names to lowercase. Empty or "
            "whitespace-only names should return None."
        ),
        "expected_changed_files": ["src/sample/normalization.py"],
        "files": {
            "pyproject.toml": """
[project]
name = "hewn-stability-003"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
            "src/sample/__init__.py": "",
            "src/sample/normalization.py": """
def normalize_name(value: str) -> str:
    return value.strip()


def stable_identifier(name: str) -> str:
    return f"user:{name}"
""",
            "tests/test_normalization.py": """
from sample.normalization import stable_identifier


def test_stable_identifier() -> None:
    assert stable_identifier("Alice") == "user:Alice"
""",
        },
    },
)


def clean_text(text: str) -> str:
    return text.lstrip("\n")


def main() -> None:
    if FIXTURES_ROOT.exists():
        shutil.rmtree(FIXTURES_ROOT)

    FIXTURES_ROOT.mkdir(parents=True)

    manifest: dict[str, Any] = {
        "experiment": "011B",
        "tasks": [],
    }

    for task in TASKS:
        task_root = FIXTURES_ROOT / task["task_id"]
        task_root.mkdir()

        files: dict[str, str] = task["files"]

        for relative, content in files.items():
            destination = task_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                clean_text(content),
                encoding="utf-8",
            )

        manifest["tasks"].append(
            {
                "task_id": task["task_id"],
                "request": task["request"],
                "fixture": task["task_id"],
                "expected_changed_files": task["expected_changed_files"],
            }
        )

    (FIXTURES_ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote {len(TASKS)} frozen fixtures to "
        f"{FIXTURES_ROOT}"
    )


if __name__ == "__main__":
    main()