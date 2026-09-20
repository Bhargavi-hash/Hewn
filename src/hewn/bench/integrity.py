from __future__ import annotations

from dataclasses import dataclass

from hewn.bench.models import AgentVisibleCase, EvaluatorOnlyCase


@dataclass(frozen=True, slots=True)
class IntegrityResult:
    passes: bool
    exposed_markers: tuple[str, ...]


def build_agent_payload(case: AgentVisibleCase) -> str:
    tools = "\n".join(
        f"- {tool_name}"
        for tool_name in case.tool_names
    )

    return (
        "TASK\n"
        f"{case.task_request}\n\n"
        "REPOSITORY CONTEXT\n"
        f"{case.repository_context}\n"
        "TOOLS\n"
        f"{tools}\n"
    )


def validate_agent_payload(
    payload: str,
    evaluator_only: EvaluatorOnlyCase,
) -> IntegrityResult:
    exposed_markers = tuple(
        marker
        for marker in evaluator_only.hidden_markers
        if marker in payload
    )

    return IntegrityResult(
        passes=not exposed_markers,
        exposed_markers=exposed_markers,
    )