from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from hewn.agent import Agent, AgentLimitError, AgentStagnationError
from hewn.authority import AuthorityGrant, AuthorityPolicy
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionRequirement
from hewn.context.builder import ContextBuilder
from hewn.execution import BubblewrapExecutionBackend
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import Model, ModelError
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.semantic import EmbeddingModel
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.sentence_transformer import (
    SentenceTransformerEmbeddingModel,
)
from hewn.retrieval.symbol_documents import build_symbol_documents
from hewn.session import HewnSession
from hewn.telemetry import AgentMetrics
from hewn.tools import ToolExecutor
from hewn.workspace import Workspace

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


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

    parser.add_argument(
        "--verify",
        action="store_true",
        help="Require a successful verification check before completion.",
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


def build_session(
    workspace_path: Path,
    *,
    model: Model,
    embedding_model: EmbeddingModel,
) -> HewnSession:
    workspace = Workspace(workspace_path)

    repository_index = RepositoryIndex.build(
        workspace.root
    )

    semantic_index = SemanticIndex.build(
        build_symbol_documents(repository_index),
        model=embedding_model,
    )

    context_builder = ContextBuilder(
        repository_root=workspace.root,
        repository_index=repository_index,
    )

    execution_backend = BubblewrapExecutionBackend()

    registry = make_builtin_tool_registry(
        workspace,
        repository_index=repository_index,
        execution_backend=execution_backend,
    )

    authority_grant = AuthorityGrant(
        repository_read=True,
        repository_write=True,
        approved_checks=True,
    )

    executor = ToolExecutor(
        registry,
        authority_policy=AuthorityPolicy(
            authority_grant
        ),
    )

    agent = Agent(
        model=model,
        registry=registry,
        executor=executor,
    )

    return HewnSession(
        agent=agent,
        repository_index=repository_index,
        semantic_index=semantic_index,
        embedding_model=embedding_model,
        context_builder=context_builder,
    )


def run_cli(
    argv: Sequence[str] | None,
    *,
    model: Model,
    embedding_model: EmbeddingModel | None = None,
    completion_requirement: CompletionRequirement | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    resolved_completion_requirement = completion_requirement

    if resolved_completion_requirement is None:
        if args.verify:
            resolved_completion_requirement = (
                CompletionRequirement.VERIFIED
            )
        else:
            resolved_completion_requirement = (
                CompletionRequirement.NONE
            )

    if embedding_model is None:
        if isinstance(model, LlamaCppModel):
            try:
                model.check_available()
            except ModelError as error:
                print(f"Model error: {error}")
                return 1
        embedding_model = SentenceTransformerEmbeddingModel(
            DEFAULT_EMBEDDING_MODEL
        )

    try:
        session = build_session(
            args.workspace,
            model=model,
            embedding_model=embedding_model,
        )

        result = session.run(
            args.request,
            completion_requirement=resolved_completion_requirement,
        )
    except (AgentLimitError, AgentStagnationError) as error:
        print(str(error))
        print()
        _print_metrics(error.metrics)

        if args.trace:
            print()
            _print_trace(error.metrics)

        return 1
    except ModelProtocolError as error:
        print(f"Model protocol error: {error}")
        return 1
    except ModelError as error:
        print(f"Model error: {error}")
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