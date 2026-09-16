from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from hewn.agent import Agent, AgentLimitError, AgentStagnationError
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionRequirement
from hewn.llama_cpp import LlamaCppModel
from hewn.models import Model
from hewn.telemetry import AgentMetrics
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


def _print_metrics(metrics: AgentMetrics) -> None:
    print(
        "Run metrics: "
        f"{metrics.model_calls} model calls, "
        f"{metrics.tool_calls} tool calls, "
        f"{metrics.successful_tool_calls} successful, "
        f"{metrics.failed_tool_calls} failed, "
        f"{metrics.wall_time_seconds:.2f}s"
    )


def _print_trace(metrics: AgentMetrics) -> None:
    print("Trace:")

    for index, event in enumerate(
        metrics.events,
        start=1,
    ):
        print(
            f"{index}. {event.kind}: {event.detail}"
        )


def run_cli(
    argv: Sequence[str] | None,
    *,
    model: Model,
    completion_requirement: CompletionRequirement = CompletionRequirement.NONE,
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

    try:
        result = agent.run(
            args.request,
            completion_requirement=completion_requirement,
        )
    except (AgentLimitError, AgentStagnationError) as error:
        print(str(error))
        print()
        _print_metrics(error.metrics)

        if args.trace:
            print()
            _print_trace(error.metrics)

        return 1

    print(result.text)
    print()
    _print_metrics(result.metrics)

    if args.trace:
        print()
        _print_trace(result.metrics)

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(
        argv,
        model=LlamaCppModel(),
    )