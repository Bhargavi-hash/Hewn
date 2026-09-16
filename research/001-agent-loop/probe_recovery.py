from pathlib import Path

from hewn.builtin_tools import make_builtin_tool_registry
from hewn.llama_cpp import LlamaCppModel
from hewn.models import Message
from hewn.workspace import Workspace


def main() -> None:
    workspace = Workspace(Path.cwd())
    registry = make_builtin_tool_registry(workspace)

    messages = [
        Message(
            role="user",
            content=(
                "Fix the failing tests. Inspect the repository, make the "
                "necessary code change, run the tests to verify the fix, "
                "and only finish after the tests pass."
            ),
        ),
        Message(
            role="assistant",
            content="Tool call: run_check {'check': 'tests'}",
        ),
        Message(
            role="tool",
            content=(
                "Error: Check failed with exit code 1\n"
                "test_add_positive_numbers: add(2, 3) returned -1 instead of 5\n"
                "test_add_negative_numbers: add(-2, -3) returned 1 instead of -5"
            ),
        ),
        Message(
            role="tool",
            content=(
                "Cannot finish because the latest verification check failed. "
                "Continue working and verify the repository again before finishing."
            ),
        ),
    ]

    model = LlamaCppModel()

    response = model.respond(
        messages=messages,
        tools=registry.definitions(),
    )

    print(repr(response))


if __name__ == "__main__":
    main()