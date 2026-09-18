from __future__ import annotations

from pathlib import Path

from hewn.builtin_tools import (
    make_builtin_tool_registry,
)
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import Message
from hewn.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]

FIXTURE_ROOT = (
    REPO_ROOT
    / "research"
    / "006-code-editing"
    / "fixtures"
    / "edit-001"
)


def main() -> int:
    workspace = Workspace(
        FIXTURE_ROOT
    )

    registry = (
        make_builtin_tool_registry(
            workspace,
            repository_index=None,
        )
    )

    model = LlamaCppModel(
        temperature=0.0,
    )

    source = (
        FIXTURE_ROOT
        / "calculator.py"
    ).read_text(
        encoding="utf-8"
    )

    request = (
        "Modify the repository to satisfy "
        "the requested behavior.\n"
        "Use the available repository tools "
        "to make the change.\n"
        "Do not modify tests. "
        "Run the tests before finishing.\n\n"
        "Task:\n"
        "Fix add so it returns the sum of "
        "its two arguments.\n\n"
        "Relevant source is supplied below. "
        "Treat it as the initial repository "
        "state. You may reread files with "
        "tools if needed.\n\n"
        "[Source 1]\n"
        "path: calculator.py\n"
        f"{source}"
    )

    try:
        response = model.respond(
            messages=[
                Message(
                    role="user",
                    content=request,
                )
            ],
            tools=registry.definitions(),
        )
    except ModelProtocolError as exc:
        print("PROTOCOL ERROR")
        print(f"reason: {exc}")
        print()
        print("RAW RESPONSE")
        print("-" * 80)
        print(repr(exc.raw_response))
        print("-" * 80)
        print()
        print("Rendered:")
        print(exc.raw_response)
        return 0

    print("VALID RESPONSE")
    print(repr(response))

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )