from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = (
    REPO_ROOT
    / "research"
    / "002-tools"
    / "results"
    / "repository-map-grounded-run-001.json"
)


def strip_markdown_fence(text: str) -> str:
    stripped = text.strip()

    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()

    if lines and lines[0].strip() in {"```", "```json"}:
        lines = lines[1:]

    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


def classify_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "not-object"

    response_type = payload.get("type")

    if response_type == "final":
        return "final"

    if response_type == "tool_call":
        name = payload.get("name")

        if isinstance(name, str):
            return f"tool_call:{name}"

        return "tool_call:missing-name"

    return "unknown-type"


def main() -> int:
    results = json.loads(
        RESULT_PATH.read_text(encoding="utf-8")
    )

    for result in results:
        if result["status"] != "ModelProtocolError":
            continue

        raw = result.get("raw_model_response")

        print("=" * 80)
        print(result["id"])

        if not isinstance(raw, str):
            print("No raw response")
            continue

        normalized = strip_markdown_fence(raw)

        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as error:
            print("Still invalid JSON after fence removal")
            print(
                f"JSON error: {error.msg} "
                f"at line {error.lineno}, column {error.colno}"
            )
            print("NORMALIZED:")
            print(normalized)
            continue

        print("Valid JSON after fence removal")
        print("Classification:", classify_payload(payload))
        print(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())