from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from hewn.action_normalizer import normalize_model_response
from hewn.model_protocol import ModelProtocolError, parse_model_response
from hewn.tools import ToolCall


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    return rows


def canonical_tool_call(call: ToolCall) -> dict[str, Any]:
    return {
        "type": "tool_call",
        "name": call.name,
        "arguments": call.arguments,
    }


def training_target_as_production(
    target_text: str,
) -> dict[str, Any] | None:
    """
    Convert the frozen M14/M15 training representation into the equivalent
    production Hewn representation for diagnostic comparison only.

    M14/M15 used:
        {"type": "tool", ...}

    Production Hewn uses:
        {"type": "tool_call", ...}

    This function does not modify the frozen datasets or their original
    evaluation metrics.
    """
    try:
        target = json.loads(target_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(target, dict):
        return None

    if set(target) != {"type", "name", "arguments"}:
        return None

    if target.get("type") != "tool":
        return None

    name = target.get("name")
    arguments = target.get("arguments")

    if not isinstance(name, str):
        return None

    if not isinstance(arguments, dict):
        return None

    return {
        "type": "tool_call",
        "name": name,
        "arguments": arguments,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    eval_rows = load_jsonl(args.eval)
    result_payload = json.loads(args.results.read_text())

    if not isinstance(result_payload, dict):
        raise TypeError("results file must contain a JSON object")

    records = result_payload.get("records")
    if not isinstance(records, list):
        raise TypeError("results file must contain a records list")

    if len(eval_rows) != len(records):
        raise ValueError(
            "eval/result length mismatch: "
            f"{len(eval_rows)} != {len(records)}"
        )

    strict_tool_calls = 0
    normalizable_outputs = 0
    normalizable_correct_actions = 0

    rules: Counter[str] = Counter()
    families: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "rows": 0,
            "strict_tool_calls": 0,
            "normalizable_outputs": 0,
            "normalizable_correct_actions": 0,
        }
    )

    diagnostic_records: list[dict[str, Any]] = []

    for eval_row, result_row in zip(
        eval_rows,
        records,
        strict=True,
    ):
        family = eval_row.get("family")
        result_family = result_row.get("family")

        if not isinstance(family, str):
            raise TypeError("eval row has invalid family")

        if result_family != family:
            raise ValueError(
                "family mismatch: "
                f"{family!r} != {result_family!r}"
            )

        raw = result_row.get("raw")
        target_text = eval_row.get("target")

        if not isinstance(raw, str):
            raise TypeError("result row has invalid raw output")

        if not isinstance(target_text, str):
            raise TypeError("eval row has invalid target")

        expected = training_target_as_production(target_text)
        if expected is None:
            raise ValueError(
                f"unsupported frozen target: {target_text!r}"
            )

        family_stats = families[family]
        family_stats["rows"] += 1

        strict_call: ToolCall | None = None

        try:
            strict_response = parse_model_response(raw)
        except ModelProtocolError:
            strict_response = None

        if isinstance(strict_response, ToolCall):
            strict_call = strict_response
            strict_tool_calls += 1
            family_stats["strict_tool_calls"] += 1

        normalized = normalize_model_response(raw)

        recovered: dict[str, Any] | None = None
        rule: str | None = None
        correct = False

        if normalized.response is not None:
            if not isinstance(normalized.response, ToolCall):
                raise ValueError(
                    "normalizer unexpectedly returned non-tool response"
                )

            normalizable_outputs += 1
            family_stats["normalizable_outputs"] += 1

            recovered = canonical_tool_call(normalized.response)
            rule = normalized.rule

            if rule is None:
                raise ValueError(
                    "normalized response is missing provenance rule"
                )

            rules[rule] += 1

            correct = recovered == expected

            if correct:
                normalizable_correct_actions += 1
                family_stats[
                    "normalizable_correct_actions"
                ] += 1

        diagnostic_records.append(
            {
                "family": family,
                "raw": raw,
                "frozen_training_target": json.loads(target_text),
                "production_equivalent_target": expected,
                "strict_production_tool_call": (
                    canonical_tool_call(strict_call)
                    if strict_call is not None
                    else None
                ),
                "normalization_rule": rule,
                "normalized_action": recovered,
                "normalized_action_correct": correct,
            }
        )

    rows = len(eval_rows)

    output = {
        "note": (
            "Post-hoc Module 16 diagnostic over frozen M15 outputs. "
            "The normalizer rules were motivated by observed M15 failure "
            "shapes, so this replay is not independent evidence of "
            "generalization and does not alter M15 metrics."
        ),
        "protocol_finding": {
            "m14_m15_tool_type": "tool",
            "production_hewn_tool_type": "tool_call",
            "aligned": False,
        },
        "rows": rows,
        "strict_tool_calls": strict_tool_calls,
        "normalizable_outputs": normalizable_outputs,
        "normalizable_correct_actions": normalizable_correct_actions,
        "normalizable_rate": (
            normalizable_outputs / rows if rows else 0.0
        ),
        "normalizable_correct_rate": (
            normalizable_correct_actions / rows if rows else 0.0
        ),
        "rules": dict(sorted(rules.items())),
        "families": {
            family: stats
            for family, stats in sorted(families.items())
        },
        "records": diagnostic_records,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2) + "\n"
    )

    print(f"Wrote {args.out}")
    print(f"rows={rows}")
    print(f"strict_tool_calls={strict_tool_calls}")
    print(f"normalizable_outputs={normalizable_outputs}")
    print(
        "normalizable_correct_actions="
        f"{normalizable_correct_actions}"
    )


if __name__ == "__main__":
    main()
