from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from hewn.model_protocol import (
    ParseSource,
    parse_model_response_with_provenance,
)
from hewn.models import (
    Message,
    ModelDiagnostic,
    ModelError,
    ModelResponse,
)
from hewn.tools import ToolDefinition


@dataclass(frozen=True)
class LlamaCppModel:
    base_url: str = "http://127.0.0.1:8080"
    temperature: float = 0.0
    max_tokens: int = 256
    timeout_seconds: float = 120.0
    health_timeout_seconds: float = 2.0
    additional_system_instruction: str | None = None

    _diagnostics: list[ModelDiagnostic] = field(
        default_factory=list,
        init=False,
        repr=False,
        compare=False,
    )

    def drain_diagnostics(self) -> list[ModelDiagnostic]:
        diagnostics = list(self._diagnostics)
        self._diagnostics.clear()
        return diagnostics

    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        payload = {
            "model": "local",
            "messages": self._build_messages(messages, tools),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        request = Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise ModelError(
                f"llama.cpp returned HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise ModelError(
                f"Could not reach llama.cpp: {exc.reason}"
            ) from exc

        generated_text = self._extract_content(body)

        return self._parse_generated_text(generated_text)

    def check_available(self) -> None:
        request = Request(
            f"{self.base_url}/health",
            method="GET",
        )
    
        try:
            with urlopen(
                request,
                timeout=self.health_timeout_seconds,
            ):
                return
        except HTTPError as exc:
            raise ModelError(
                f"llama.cpp health check returned HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise ModelError(
                f"Could not reach llama.cpp: {exc.reason}"
            ) from exc


    def _parse_generated_text(
        self,
        generated_text: str,
    ) -> ModelResponse:
        parsed = parse_model_response_with_provenance(
            generated_text
        )

        if parsed.source is ParseSource.CANONICAL:
            detail = "canonical"
        else:
            if parsed.normalization_rule is None:
                raise RuntimeError(
                    "Normalized response is missing provenance"
                )

            detail = (
                "normalized:"
                f"{parsed.normalization_rule}"
            )

        self._diagnostics.append(
            ModelDiagnostic(
                kind="model_protocol",
                detail=detail,
            )
        )

        return parsed.response

    def _build_messages(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> list[dict[str, str]]:
        system_prompt = self._build_system_prompt(tools)

        provider_messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        provider_messages.extend(
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        )

        return provider_messages

    def _build_system_prompt(
        self,
        tools: list[ToolDefinition],
    ) -> str:
        tool_descriptions = "\n".join(
            (
                f"- {tool.name}: {tool.description}\n"
                f"  arguments schema: "
                f"{json.dumps(tool.input_schema, sort_keys=True)}"
            )
            for tool in tools
        )

        system_prompt = (
            "You are the decision model inside Hewn, a coding agent.\n"
            "Choose exactly one next action.\n\n"
            "To use a tool, respond with exactly this JSON shape:\n"
            '{"type":"tool_call","name":"TOOL_NAME",'
            '"arguments":{...}}\n\n'
            "To finish, respond with exactly this JSON shape:\n"
            '{"type":"final","text":"ANSWER"}\n\n'
            "Return exactly one JSON object and no Markdown fences, "
            "explanation, or additional text.\n\n"
            "Available tools:\n"
            f"{tool_descriptions}"
        )

        if self.additional_system_instruction is not None:
            system_prompt += (
                "\n\n"
                + self.additional_system_instruction
            )

        return system_prompt

    def _extract_content(self, body: str) -> str:
        try:
            payload: Any = json.loads(body)
            content = payload["choices"][0]["message"]["content"]
        except (
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise ModelError(
                "llama.cpp returned an invalid chat response"
            ) from exc

        if not isinstance(content, str):
            raise ModelError(
                "llama.cpp returned non-text assistant content"
            )

        return content