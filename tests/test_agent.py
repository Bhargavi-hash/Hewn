from pathlib import Path

import pytest

from hewn.agent import Agent, AgentLimitError
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.models import FinalResponse, Message, ModelResponse
from hewn.tools import ToolCall, ToolDefinition, ToolExecutor
from hewn.workspace import Workspace


class ScriptedModel:
    def __init__(
        self,
        responses: list[ModelResponse],
    ) -> None:
        self._responses = iter(responses)
        self.calls: list[list[Message]] = []

    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        self.calls.append(list(messages))
        return next(self._responses)


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
    ):
        agent.run("Keep looking.")

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