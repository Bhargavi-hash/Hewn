from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = MODULE_ROOT / "fixtures"


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_configuration() -> dict[str, Any]:
    root = FIXTURES_ROOT / "configuration"
    shutil.rmtree(root, ignore_errors=True)

    write(
        root,
        "src/sample/__init__.py",
        "",
    )

    write(
        root,
        "src/sample/settings.py",
        """DEFAULT_RETRY_COUNT = 2
DEFAULT_REQUEST_TIMEOUT_SECONDS = 5
""",
    )

    write(
        root,
        "src/sample/client.py",
        """from sample.settings import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_RETRY_COUNT,
)


def request_policy() -> tuple[int, int]:
    return (
        DEFAULT_RETRY_COUNT,
        DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )
""",
    )

    write(
        root,
        "tests/test_client.py",
        """from sample.client import request_policy


def test_request_policy_defaults() -> None:
    assert request_policy() == (2, 5)
""",
    )

    write(
        root,
        "pyproject.toml",
        """[tool.pytest.ini_options]
pythonpath = ["src"]
""",
    )

    return {
        "id": "configuration",
        "fixture": "configuration",
        "tasks": [
            {
                "id": "config-001",
                "request": (
                    "Increase the default retry count from 2 to 4 "
                    "without changing request timeout behavior."
                ),
                "required_changed_files": [
                    "src/sample/settings.py"
                ],
                "allowed_changed_files": [
                    "src/sample/settings.py"
                ],
                "reusable_files": [
                    "src/sample/settings.py",
                    "src/sample/client.py",
                    "tests/test_client.py",
                ],
                "expected_after": {
                    "src/sample/settings.py": (
                        "DEFAULT_RETRY_COUNT = 4\n"
                        "DEFAULT_REQUEST_TIMEOUT_SECONDS = 5\n"
                    )
                },
            },
            {
                "id": "config-002",
                "request": (
                    "Increase the default request timeout from "
                    "5 seconds to 10 seconds without changing "
                    "retry behavior."
                ),
                "required_changed_files": [
                    "src/sample/settings.py"
                ],
                "allowed_changed_files": [
                    "src/sample/settings.py"
                ],
                "reusable_files": [
                    "src/sample/settings.py",
                    "src/sample/client.py",
                    "tests/test_client.py",
                ],
                "expected_after": {
                    "src/sample/settings.py": (
                        "DEFAULT_RETRY_COUNT = 4\n"
                        "DEFAULT_REQUEST_TIMEOUT_SECONDS = 10\n"
                    )
                },
            },
        ],
    }


def build_serialization() -> dict[str, Any]:
    root = FIXTURES_ROOT / "serialization"
    shutil.rmtree(root, ignore_errors=True)

    write(
        root,
        "src/sample/__init__.py",
        "",
    )

    write(
        root,
        "src/sample/schema.py",
        """USER_ID_FIELD = "user_id"
""",
    )

    write(
        root,
        "src/sample/serializer.py",
        """from sample.schema import USER_ID_FIELD


def serialize_user(user_id: int) -> dict[str, object]:
    return {
        USER_ID_FIELD: user_id,
    }
""",
    )

    write(
        root,
        "tests/test_serializer.py",
        """from sample.serializer import serialize_user


def test_serialize_user() -> None:
    assert serialize_user(7) == {
        "user_id": 7,
    }
""",
    )

    write(
        root,
        "pyproject.toml",
        """[tool.pytest.ini_options]
pythonpath = ["src"]
""",
    )

    return {
        "id": "serialization",
        "fixture": "serialization",
        "tasks": [
            {
                "id": "serialization-001",
                "request": (
                    "Rename the serialized user identifier from "
                    "user_id to account_id while keeping the "
                    "serializer input parameter named user_id."
                ),
                "required_changed_files": [
                    "src/sample/schema.py",
                    "src/sample/serializer.py",
                ],
                "allowed_changed_files": [
                    "src/sample/schema.py",
                    "src/sample/serializer.py",
                ],
                "reusable_files": [
                    "src/sample/schema.py",
                    "src/sample/serializer.py",
                    "tests/test_serializer.py",
                ],
                "expected_after": {
                    "src/sample/schema.py": (
                        'ACCOUNT_ID_FIELD = "account_id"\n'
                    ),
                    "src/sample/serializer.py": (
                        "from sample.schema import ACCOUNT_ID_FIELD\n\n\n"
                        "def serialize_user(user_id: int) "
                        "-> dict[str, object]:\n"
                        "    return {\n"
                        "        ACCOUNT_ID_FIELD: user_id,\n"
                        "    }\n"
                    ),
                },
            },
            {
                "id": "serialization-002",
                "request": (
                    "Add the serialized field active with the "
                    "boolean value passed to serialize_user. "
                    "Keep the existing account_id field unchanged."
                ),
                "required_changed_files": [
                    "src/sample/serializer.py"
                ],
                "allowed_changed_files": [
                    "src/sample/serializer.py"
                ],
                "reusable_files": [
                    "src/sample/schema.py",
                    "src/sample/serializer.py",
                    "tests/test_serializer.py",
                ],
                "expected_contains": {
                    "src/sample/serializer.py": [
                        "def serialize_user(user_id: int, active: bool)",
                        '"active": active',
                    ]
                },
            },
        ],
    }


def build_parser() -> dict[str, Any]:
    root = FIXTURES_ROOT / "parser"
    shutil.rmtree(root, ignore_errors=True)

    write(
        root,
        "src/sample/__init__.py",
        "",
    )

    write(
        root,
        "src/sample/parser.py",
        """def normalize_value(value: str) -> str:
    return value.strip()
""",
    )

    write(
        root,
        "tests/test_parser.py",
        """from sample.parser import normalize_value


def test_normalize_value_trims_whitespace() -> None:
    assert normalize_value("  Alpha  ") == "Alpha"
""",
    )

    write(
        root,
        "pyproject.toml",
        """[tool.pytest.ini_options]
pythonpath = ["src"]
""",
    )

    return {
        "id": "parser",
        "fixture": "parser",
        "tasks": [
            {
                "id": "parser-001",
                "request": (
                    "Make normalized parser values case-insensitive "
                    "by lowercasing them after trimming whitespace."
                ),
                "required_changed_files": [
                    "src/sample/parser.py"
                ],
                "allowed_changed_files": [
                    "src/sample/parser.py"
                ],
                "reusable_files": [
                    "src/sample/parser.py",
                    "tests/test_parser.py",
                ],
                "expected_after": {
                    "src/sample/parser.py": (
                        "def normalize_value(value: str) -> str:\n"
                        "    return value.strip().lower()\n"
                    )
                },
            },
            {
                "id": "parser-002",
                "request": (
                    "Treat an empty normalized value as None while "
                    "preserving the existing normalization behavior "
                    "for non-empty values."
                ),
                "required_changed_files": [
                    "src/sample/parser.py"
                ],
                "allowed_changed_files": [
                    "src/sample/parser.py"
                ],
                "reusable_files": [
                    "src/sample/parser.py",
                    "tests/test_parser.py",
                ],
                "expected_contains": {
                    "src/sample/parser.py": [
                        "str | None",
                        "return normalized or None",
                    ]
                },
            },
        ],
    }


def main() -> None:
    FIXTURES_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = {
        "version": 1,
        "experiment": "010A",
        "pairs": [
            build_configuration(),
            build_serialization(),
            build_parser(),
        ],
    }

    manifest_path = FIXTURES_ROOT / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote fixtures and manifest to "
        f"{FIXTURES_ROOT}"
    )


if __name__ == "__main__":
    main()