from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class PlanningProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class PlannedFile:
    path: str
    symbols: tuple[str, ...]
    operations: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    files: tuple[PlannedFile, ...]
    verification: tuple[str, ...]


def _require_string_list(
    value: Any,
    *,
    field: str,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PlanningProtocolError(
            f"{field} must be an array"
        )

    if not all(
        isinstance(item, str) and item.strip()
        for item in value
    ):
        raise PlanningProtocolError(
            f"{field} must contain non-empty strings"
        )

    return tuple(value)


def parse_plan(text: str) -> Plan:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanningProtocolError(
            f"invalid JSON: {exc.msg}"
        ) from exc

    if not isinstance(value, dict):
        raise PlanningProtocolError(
            "plan must be a JSON object"
        )

    if set(value) != {"files", "verification"}:
        raise PlanningProtocolError(
            "plan must contain exactly files and verification"
        )

    raw_files = value["files"]
    if not isinstance(raw_files, list) or not raw_files:
        raise PlanningProtocolError(
            "files must be a non-empty array"
        )

    files: list[PlannedFile] = []
    seen_paths: set[str] = set()

    for index, raw_file in enumerate(raw_files):
        if not isinstance(raw_file, dict):
            raise PlanningProtocolError(
                f"files[{index}] must be an object"
            )

        if set(raw_file) != {
            "path",
            "symbols",
            "operations",
        }:
            raise PlanningProtocolError(
                f"files[{index}] must contain exactly "
                "path, symbols, and operations"
            )

        path = raw_file["path"]
        if not isinstance(path, str) or not path.strip():
            raise PlanningProtocolError(
                f"files[{index}].path must be a "
                "non-empty string"
            )

        if path in seen_paths:
            raise PlanningProtocolError(
                f"duplicate planned file: {path}"
            )

        seen_paths.add(path)

        symbols = _require_string_list(
            raw_file["symbols"],
            field=f"files[{index}].symbols",
        )
        operations = _require_string_list(
            raw_file["operations"],
            field=f"files[{index}].operations",
        )

        if not operations:
            raise PlanningProtocolError(
                f"files[{index}].operations must not be empty"
            )

        files.append(
            PlannedFile(
                path=path,
                symbols=symbols,
                operations=operations,
            )
        )

    verification = _require_string_list(
        value["verification"],
        field="verification",
    )

    if not verification:
        raise PlanningProtocolError(
            "verification must not be empty"
        )

    return Plan(
        files=tuple(files),
        verification=verification,
    )