from dataclasses import dataclass, field
from pathlib import Path

import pytest

from hewn.agent import (
    Agent,
    AgentLimitError,
    AgentStagnationError,
)
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionPolicy, CompletionRequirement
from hewn.models import (
    FinalResponse,
    Message,
    ModelDiagnostic,
    ModelResponse,
)
from hewn.telemetry import AgentEvent
from hewn.tools import (
    ToolCall,
    ToolDefinition,
    ToolExecutor,
    ToolResult,
)
from hewn.workspace import Workspace


@dataclass
class RecordingCompletionRejectionFormatter:
    calls: list[tuple[FinalResponse, str]] = field(
        default_factory=list
    )

    def __call__(
        self,
        response: FinalResponse,
        reason: str,
    ) -> list[Message]:
        self.calls.append((response, reason))

        return [
            Message(
                role="user",
                content=f"Controller feedback: {reason}",
            )
        ]


class ScriptedModel:
    def __init__(
        self,
        responses: list[ModelResponse],
    ) -> None:
        self.received_messages: list[list[Message]] = []
        self._responses = iter(responses)
        self.calls: list[list[Message]] = []

    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        self.received_messages.append(list(messages))
        self.calls.append(list(messages))
        return next(self._responses)

class DiagnosticScriptedModel(ScriptedModel):
    def __init__(
        self,
        responses: list[ModelResponse],
        diagnostics: list[ModelDiagnostic],
    ) -> None:
        super().__init__(responses)
        self._diagnostics = diagnostics

    def drain_diagnostics(self) -> list[ModelDiagnostic]:
        diagnostics = list(self._diagnostics)
        self._diagnostics.clear()
        return diagnostics

def make_agent(
    tmp_path: Path,
    model: ScriptedModel,
    *,
    max_turns: int = 20,
) -> Agent:
    workspace = Workspace(tmp_path)
    registry = make_builtin_tool_registry(workspace)

    return Agent(
        model=model,
        registry=registry,
        executor=ToolExecutor(registry),
        max_turns=max_turns,
    )

def test_agent_records_model_diagnostics(
    tmp_path: Path,
) -> None:
    model = DiagnosticScriptedModel(
        responses=[
            FinalResponse("Done."),
        ],
        diagnostics=[
            ModelDiagnostic(
                kind="model_protocol",
                detail=(
                    "normalized:"
                    "action_file_to_read_file"
                ),
            ),
        ],
    )

    agent = make_agent(tmp_path, model)

    result = agent.run("Finish.")

    assert result.metrics.events[0] == AgentEvent(
        kind="model_protocol",
        detail=(
            "normalized:"
            "action_file_to_read_file"
        ),
    )

    assert result.metrics.events[1].kind == "model_response"

def test_agent_returns_immediate_final_response(
    tmp_path: Path,
) -> None:
    model = ScriptedModel(
        responses=[
            FinalResponse("Done."),
        ]
    )

    agent = make_agent(tmp_path, model)

    result = agent.run("Say done.")

    assert result.text == "Done."
    assert len(model.calls) == 1

def test_agent_executes_tool_and_returns_observation_to_model(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "class ImportantThing:\n"
        "    pass\n",
        encoding="utf-8",
    )

    model = ScriptedModel(
        responses=[
            ToolCall(
                name="search_text",
                arguments={"query": "ImportantThing"},
            ),
            FinalResponse("Found it."),
        ]
    )

    agent = make_agent(tmp_path, model)

    result = agent.run("Find ImportantThing.")

    assert result.text == "Found it."
    assert len(model.calls) == 2

    second_call_messages = model.calls[1]

    assert any(
        message.role == "tool"
        and "example.py" in message.content
        and "ImportantThing" in message.content
        for message in second_call_messages
    )

def test_agent_returns_tool_failure_to_model(
    tmp_path: Path,
) -> None:
    model = ScriptedModel(
        responses=[
            ToolCall(
                name="read_file",
                arguments={"path": "missing.py"},
            ),
            FinalResponse("I recovered."),
        ]
    )

    agent = make_agent(tmp_path, model)

    result = agent.run("Read the file.")

    assert result.text == "I recovered."

    second_call_messages = model.calls[1]

    assert any(
        message.role == "tool"
        and "Error: File not found: missing.py" in message.content
        for message in second_call_messages
    )

def test_agent_stops_at_turn_limit(
    tmp_path: Path,
) -> None:
    model = ScriptedModel(
        responses=[
            ToolCall(
                name="list_directory",
                arguments={"path": "."},
            ),
            ToolCall(
                name="list_directory",
                arguments={"path": "."},
            ),
        ]
    )

    agent = make_agent(
        tmp_path,
        model,
        max_turns=2,
    )

    with pytest.raises(
        AgentLimitError,
        match="Agent exceeded maximum turns: 2",
    ) as exc_info:
        agent.run("Keep looking.")

    error = exc_info.value

    assert error.metrics.model_calls == 2
    assert error.metrics.tool_calls == 2
    assert error.metrics.successful_tool_calls == 2
    assert error.metrics.failed_tool_calls == 0
    assert error.metrics.wall_time_seconds >= 0
    assert len(error.metrics.events) == 4

def test_agent_records_model_and_tool_metrics(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "class ImportantThing:\n"
        "    pass\n",
        encoding="utf-8",
    )

    model = ScriptedModel(
        responses=[
            ToolCall(
                name="search_text",
                arguments={"query": "ImportantThing"},
            ),
            ToolCall(
                name="read_file",
                arguments={"path": "missing.py"},
            ),
            FinalResponse("Finished."),
        ]
    )

    agent = make_agent(tmp_path, model)

    result = agent.run("Investigate ImportantThing.")

    assert result.text == "Finished."

    assert result.metrics.model_calls == 3
    assert result.metrics.tool_calls == 2
    assert result.metrics.successful_tool_calls == 1
    assert result.metrics.failed_tool_calls == 1
    assert result.metrics.wall_time_seconds >= 0

def test_agent_records_execution_trace(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "class ImportantThing:\n"
        "    pass\n",
        encoding="utf-8",
    )

    model = ScriptedModel(
        responses=[
            ToolCall(
                name="search_text",
                arguments={"query": "ImportantThing"},
            ),
            FinalResponse("Found it."),
        ]
    )

    agent = make_agent(tmp_path, model)

    result = agent.run("Find ImportantThing.")

    assert len(result.metrics.events) == 3

    assert result.metrics.events[0].kind == (
        "model_response"
    )
    assert "search_text" in (
        result.metrics.events[0].detail
    )

    assert result.metrics.events[1].kind == (
        "tool_result"
    )
    assert "example.py" in (
        result.metrics.events[1].detail
    )

    assert result.metrics.events[2].kind == (
        "model_response"
    )
    assert "Found it." in (
        result.metrics.events[2].detail
    )

def test_rejects_final_response_after_failed_check(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_failure.py").write_text(
        "def test_failure() -> None:\n"
        "    assert False\n",
        encoding="utf-8",
    )

    model = ScriptedModel(
        responses=[
            ToolCall(
                name="run_check",
                arguments={"check": "tests"},
            ),
            FinalResponse(text="The tests failed."),
            FinalResponse(text="Unable to continue."),
        ]
    )

    agent = make_agent(
        tmp_path,
        model,
        max_turns=3,
    )

    with pytest.raises(
        AgentLimitError,
        match="Agent exceeded maximum turns: 3",
    ):
        agent.run("Fix the failing tests.")

    assert len(model.calls) == 3

    third_call_messages = model.calls[2]

    assert any(
        message.role == "tool"
        and "Cannot finish because the latest verification check failed."
        in message.content
        for message in third_call_messages
    )

def test_rejects_final_response_after_repository_change(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    model = ScriptedModel(
        responses=[
            ToolCall(
                name="replace_text",
                arguments={
                    "path": "example.py",
                    "old": "value = 1",
                    "new": "value = 2",
                },
            ),
            FinalResponse(text="Done."),
            FinalResponse(text="Still done."),
        ]
    )

    agent = make_agent(
        tmp_path,
        model,
        max_turns=3,
    )

    with pytest.raises(
        AgentLimitError,
        match="Agent exceeded maximum turns: 3",
    ):
        agent.run("Change the value.")

    assert (tmp_path / "example.py").read_text(
        encoding="utf-8"
    ) == "value = 2\n"

    third_call_messages = model.calls[2]

    assert any(
        message.role == "tool"
        and "repository changed" in message.content
        and "verification" in message.content
        for message in third_call_messages
    )

def test_accepts_final_response_after_edit_and_successful_check(
    tmp_path: Path,
) -> None:
    (tmp_path / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a - b\n",
        encoding="utf-8",
    )

    (tmp_path / "test_calculator.py").write_text(
        "from calculator import add\n\n"
        "def test_add() -> None:\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    model = ScriptedModel(
        responses=[
            ToolCall(
                name="run_check",
                arguments={"check": "tests"},
            ),
            ToolCall(
                name="replace_text",
                arguments={
                    "path": "calculator.py",
                    "old": "return a - b",
                    "new": "return a + b",
                },
            ),
            ToolCall(
                name="run_check",
                arguments={"check": "tests"},
            ),
            FinalResponse(text="Fixed and verified."),
        ]
    )

    agent = make_agent(
        tmp_path,
        model,
        max_turns=4,
    )

    result = agent.run("Fix the failing tests.")

    assert result.text == "Fixed and verified."

    assert (tmp_path / "calculator.py").read_text(
        encoding="utf-8"
    ) == (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )

    assert result.metrics.model_calls == 4
    assert result.metrics.tool_calls == 3

class RecordingCompletionPolicy(CompletionPolicy):
    def __init__(
        self,
        *,
        requirement: CompletionRequirement,
    ) -> None:
        super().__init__(requirement=requirement)
        self.attempts: list[tuple[str, bool]] = []

    def record_tool_attempt(
        self,
        *,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        self.attempts.append(
            (call.name, result.ok)
        )


def test_agent_injects_completion_policy_and_records_failed_tool_attempt(
    tmp_path: Path,
) -> None:
    created: list[RecordingCompletionPolicy] = []

    def make_policy(
        requirement: CompletionRequirement,
    ) -> CompletionPolicy:
        policy = RecordingCompletionPolicy(
            requirement=requirement,
        )
        created.append(policy)
        return policy

    model = ScriptedModel(
        responses=[
            ToolCall(
                name="replace_text",
                arguments={
                    "path": "missing.py",
                    "old": "a",
                    "new": "b",
                },
            ),
            FinalResponse("Done."),
        ]
    )

    workspace = Workspace(tmp_path)
    registry = make_builtin_tool_registry(workspace)

    agent = Agent(
        model=model,
        registry=registry,
        executor=ToolExecutor(registry),
        completion_policy_factory=make_policy,
    )

    result = agent.run("Attempt an edit.")

    assert result.text == "Done."
    assert len(created) == 1
    assert created[0].attempts == [
        ("replace_text", False)
    ]


def test_default_completion_factory_preserves_existing_behavior(
    tmp_path: Path,
) -> None:
    model = ScriptedModel(
        responses=[
            FinalResponse("Done."),
        ]
    )

    agent = make_agent(tmp_path, model)

    result = agent.run("Say done.")

    assert result.text == "Done."

def test_default_completion_rejection_formatter_preserves_existing_behavior(
    tmp_path: Path,
) -> None:
    model = ScriptedModel(
        responses=[
            FinalResponse(text="premature completion"),
            FinalResponse(text="still premature"),
            FinalResponse(text="still premature"),
        ]
    )

    registry = make_builtin_tool_registry(
        Workspace(tmp_path)
    )
    executor = ToolExecutor(registry)

    agent = Agent(
        model=model,
        registry=registry,
        executor=executor,
    )

    with pytest.raises(AgentStagnationError):
        agent.run(
            "Change the repository.",
            completion_requirement=CompletionRequirement.VERIFIED,
        )

    assert len(model.received_messages) >= 2

    second_messages = model.received_messages[1]

    assert second_messages[0] == Message(
        role="user",
        content="Change the repository.",
    )

    assert second_messages[-1].role == "tool"
    assert "verification" in second_messages[-1].content.lower()

    assert all(
        message.content != "premature completion"
        for message in second_messages
    )


def test_completion_rejection_formatter_is_injectable(
    tmp_path: Path,
) -> None:
    formatter = RecordingCompletionRejectionFormatter()

    model = ScriptedModel(
        responses=[
            FinalResponse(text="premature completion"),
            FinalResponse(text="still premature"),
            FinalResponse(text="still premature"),
        ]
    )

    registry = make_builtin_tool_registry(
        Workspace(tmp_path)
    )
    executor = ToolExecutor(registry)

    agent = Agent(
        model=model,
        registry=registry,
        executor=executor,
        completion_rejection_formatter=formatter,
    )

    with pytest.raises(AgentStagnationError):
        agent.run(
            "Change the repository.",
            completion_requirement=CompletionRequirement.VERIFIED,
        )

    assert formatter.calls

    rejected_response, reason = formatter.calls[0]

    assert rejected_response == FinalResponse(
        text="premature completion"
    )
    assert "verification" in reason.lower()

    second_messages = model.received_messages[1]

    assert second_messages[-1] == Message(
        role="user",
        content=f"Controller feedback: {reason}",
    )