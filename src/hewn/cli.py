from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from hewn.agent import Agent
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.llama_cpp import LlamaCppModel
from hewn.models import Model
from hewn.tools import ToolExecutor
from hewn.workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hewn",
        description=(
            "A local-first coding agent designed to make "
            "small models perform far above their weight."
        ),
    )

    parser.add_argument(
        "request",
        help="Coding task or question for Hewn.",
    )

    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Repository workspace. Defaults to the current directory.",
    )

    parser.add_argument(
        "--trace",
        action="store_true",
        help="Show the agent execution trace.",
    )

    return parser


def run_cli(
    argv: Sequence[str] | None,
    *,
    model: Model,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    workspace = Workspace(args.workspace)
    registry = make_builtin_tool_registry(workspace)
    executor = ToolExecutor(registry)

    agent = Agent(
        model=model,
        registry=registry,
        executor=executor,
    )

    result = agent.run(args.request)

    print(result.text)
    print()
    print(
        "Run metrics: "
        f"{result.metrics.model_calls} model calls, "
        f"{result.metrics.tool_calls} tool calls, "
        f"{result.metrics.successful_tool_calls} successful, "
        f"{result.metrics.failed_tool_calls} failed, "
        f"{result.metrics.wall_time_seconds:.2f}s"
    )

    if args.trace:
        print()
        print("Trace:")

        for index, event in enumerate(
            result.metrics.events,
            start=1,
        ):
            print(
                f"{index}. {event.kind}: {event.detail}"
            )

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(
        argv,
        model=LlamaCppModel(),
    )