from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from hewn.agent import Agent
from hewn.context.models import (
    ContextBundle,
    ContextEvidence,
)
from hewn.models import (
    FinalResponse,
    Message,
    ModelResponse,
)
from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
)
from hewn.tools import (
    ToolDefinition,
    ToolExecutor,
    ToolRegistry,
)


class RecordingModel:
    def __init__(self) -> None:
        self.messages: Sequence[Message] | None = None

    def respond(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
    ) -> ModelResponse:
        self.messages = messages

        return FinalResponse(
            text="done"
        )


def _context() -> ContextBundle:
    result = RetrievalResult(
        document=RepositoryDocument(
            path=PurePosixPath(
                "src/hewn/tools.py"
            ),
            symbol="ToolExecutor",
            text=(
                "class ToolExecutor:\n"
                "    pass"
            ),
        ),
        score=0.91,
    )

    return ContextBundle(
        evidence=(
            ContextEvidence(
                retrieval_result=result,
            ),
        )
    )


def test_agent_preserves_plain_request_without_context() -> None:
    model = RecordingModel()
    registry = ToolRegistry()

    agent = Agent(
        model=model,
        registry=registry,
        executor=ToolExecutor(
            registry=registry,
        ),
    )

    result = agent.run(
        "Find ToolExecutor."
    )

    assert result.text == "done"
    assert model.messages is not None
    assert len(model.messages) == 1
    assert (
        model.messages[0].content
        == "Find ToolExecutor."
    )


def test_agent_injects_prepared_repository_context() -> None:
    model = RecordingModel()
    registry = ToolRegistry()

    agent = Agent(
        model=model,
        registry=registry,
        executor=ToolExecutor(
            registry=registry,
        ),
    )

    result = agent.run(
        "Find ToolExecutor.",
        context=_context(),
    )

    assert result.text == "done"
    assert model.messages is not None

    content = model.messages[0].content

    assert "Find ToolExecutor." in content
    assert "Relevant repository evidence" in content
    assert "[Repository evidence 1]" in content
    assert "src/hewn/tools.py" in content
    assert "ToolExecutor" in content
    assert "class ToolExecutor:" in content


def test_agent_does_not_inject_empty_context() -> None:
    model = RecordingModel()
    registry = ToolRegistry()

    agent = Agent(
        model=model,
        registry=registry,
        executor=ToolExecutor(
            registry=registry,
        ),
    )

    agent.run(
        "Find ToolExecutor.",
        context=ContextBundle(
            evidence=()
        ),
    )

    assert model.messages is not None
    assert (
        model.messages[0].content
        == "Find ToolExecutor."
    )


def test_context_format_does_not_expose_retrieval_score() -> None:
    formatted = _context().format_for_model()

    assert "0.91" not in formatted
    assert "score" not in formatted.lower()