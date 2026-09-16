from __future__ import annotations

from hewn.cli import run_cli
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError

BEHAVIORAL_INSTRUCTION = (
    "Use tools when the task requires information from or changes "
    "to the repository.\n"
    "A final response means the requested task is complete, not "
    "that you intend to begin it.\n"
    "Do not claim completion until you have performed the required "
    "repository actions.\n"
    "For coding tasks, inspect relevant repository evidence before editing.\n"
    "If the task requests verification, run an available check before finishing."
)


def main() -> int:
    model = LlamaCppModel(
        additional_system_instruction=BEHAVIORAL_INSTRUCTION,
    )

    try:
        return run_cli(
            None,
            model=model,
        )
    except ModelProtocolError as error:
        print(f"MODEL PROTOCOL ERROR: {error}")
        print()
        print("RAW MODEL RESPONSE:")
        print(repr(error.raw_response))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())