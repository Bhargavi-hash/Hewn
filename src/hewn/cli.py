from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from hewn.agent import Agent
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.models import EchoModel
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

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    workspace = Workspace(args.workspace)
    registry = make_builtin_tool_registry(workspace)
    executor = ToolExecutor(registry)
    model = EchoModel()

    agent = Agent(
        model=model,
        registry=registry,
        executor=executor,
    )

    result = agent.run(args.request)

    print(result.text)

    return 0