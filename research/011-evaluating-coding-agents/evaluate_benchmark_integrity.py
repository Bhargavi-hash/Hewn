from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Final

MODULE_ROOT: Final = Path(__file__).resolve().parent
OUTPUT_PATH: Final = (
    MODULE_ROOT
    / "results"
    / "011e-benchmark-integrity-run001.json"
)


@dataclass(frozen=True, slots=True)
class AgentVisibleCase:
    task_request: str
    repository_context: str
    tool_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluatorOnlyCase:
    behavioral_assertions: tuple[str, ...]
    regression_assertions: tuple[str, ...]
    expected_changed_files: tuple[str, ...]
    expected_patch_markers: tuple[str, ...]
    scoring_metadata: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntegrityResult:
    condition: str
    payload_constructed: bool
    hidden_markers_exposed: bool
    integrity_passes: bool
    exposed_markers: tuple[str, ...]
    matches_expected: bool


@dataclass(frozen=True, slots=True)
class ExpectedResult:
    payload_constructed: bool
    hidden_markers_exposed: bool
    integrity_passes: bool


AGENT_VISIBLE: Final = AgentVisibleCase(
    task_request=(
        "Normalize non-empty names by stripping surrounding whitespace "
        "and converting them to lowercase. Empty or whitespace-only "
        "names should return None. Preserve all other behavior."
    ),
    repository_context="""\
src/sample/normalization.py

def normalize_name(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    return normalized
""",
    tool_names=(
        "read_file",
        "search_text",
        "replace_text",
        "run_check",
    ),
)


EVALUATOR_ONLY: Final = EvaluatorOnlyCase(
    behavioral_assertions=(
        'normalize_name(" Alice ") == "alice"',
        'normalize_name(" BOB ") == "bob"',
        'normalize_name("   ") is None',
    ),
    regression_assertions=(
        'stable_identifier("Alice") == "user:Alice"',
        'stable_identifier("BOB") == "user:BOB"',
    ),
    expected_changed_files=(
        "src/sample/normalization.py",
    ),
    expected_patch_markers=(
        "return normalized.lower()",
    ),
    scoring_metadata=(
        "primary_success = task_passes AND regression_passes",
    ),
)


EXPECTED_CHANGED_FILE_MARKERS: Final = tuple(
    f"{path}::expected_changed_file"
    for path in EVALUATOR_ONLY.expected_changed_files
)


HIDDEN_MARKERS: Final = (
    *EVALUATOR_ONLY.behavioral_assertions,
    *EVALUATOR_ONLY.regression_assertions,
    *EXPECTED_CHANGED_FILE_MARKERS,
    *EVALUATOR_ONLY.expected_patch_markers,
    *EVALUATOR_ONLY.scoring_metadata,
)


EXPECTED: Final[dict[str, ExpectedResult]] = {
    "A_clean": ExpectedResult(
        payload_constructed=True,
        hidden_markers_exposed=False,
        integrity_passes=True,
    ),
    "B_hidden_oracle": ExpectedResult(
        payload_constructed=True,
        hidden_markers_exposed=True,
        integrity_passes=False,
    ),
    "C_expected_patch": ExpectedResult(
        payload_constructed=True,
        hidden_markers_exposed=True,
        integrity_passes=False,
    ),
    "D_scoring_metadata": ExpectedResult(
        payload_constructed=True,
        hidden_markers_exposed=True,
        integrity_passes=False,
    ),
}


def build_agent_payload(case: AgentVisibleCase) -> str:
    tools = "\n".join(f"- {name}" for name in case.tool_names)

    return (
        "TASK\n"
        f"{case.task_request}\n\n"
        "REPOSITORY CONTEXT\n"
        f"{case.repository_context}\n"
        "TOOLS\n"
        f"{tools}\n"
    )


def find_hidden_markers(payload: str) -> tuple[str, ...]:
    return tuple(
        marker
        for marker in HIDDEN_MARKERS
        if marker in payload
    )


def evaluate_condition(
    condition: str,
    case: AgentVisibleCase,
) -> IntegrityResult:
    payload = build_agent_payload(case)
    exposed_markers = find_hidden_markers(payload)

    payload_constructed = bool(payload)
    hidden_markers_exposed = bool(exposed_markers)
    integrity_passes = not hidden_markers_exposed

    expected = EXPECTED[condition]

    matches_expected = (
        payload_constructed == expected.payload_constructed
        and hidden_markers_exposed
        == expected.hidden_markers_exposed
        and integrity_passes == expected.integrity_passes
    )

    return IntegrityResult(
        condition=condition,
        payload_constructed=payload_constructed,
        hidden_markers_exposed=hidden_markers_exposed,
        integrity_passes=integrity_passes,
        exposed_markers=exposed_markers,
        matches_expected=matches_expected,
    )


def make_conditions() -> tuple[
    tuple[str, AgentVisibleCase],
    ...,
]:
    clean = AGENT_VISIBLE

    hidden_oracle = replace(
        AGENT_VISIBLE,
        repository_context=(
            AGENT_VISIBLE.repository_context
            + "\n"
            + EVALUATOR_ONLY.behavioral_assertions[0]
            + "\n"
        ),
    )

    expected_patch = replace(
        AGENT_VISIBLE,
        task_request=(
            AGENT_VISIBLE.task_request
            + "\n"
            + EVALUATOR_ONLY.expected_patch_markers[0]
        ),
    )

    scoring_metadata = replace(
        AGENT_VISIBLE,
        repository_context=(
            AGENT_VISIBLE.repository_context
            + "\n"
            + EVALUATOR_ONLY.scoring_metadata[0]
            + "\n"
        ),
    )

    return (
        ("A_clean", clean),
        ("B_hidden_oracle", hidden_oracle),
        ("C_expected_patch", expected_patch),
        ("D_scoring_metadata", scoring_metadata),
    )


def main() -> None:
    conditions = make_conditions()

    results = tuple(
        evaluate_condition(condition, case)
        for condition, case in conditions
    )

    expected_matrix_matches = sum(
        result.matches_expected
        for result in results
    )

    clean_results = tuple(
        result
        for result in results
        if result.condition == "A_clean"
    )

    contaminated_results = tuple(
        result
        for result in results
        if result.condition != "A_clean"
    )

    clean_payloads = sum(
        result.integrity_passes
        for result in clean_results
    )

    contaminated_payloads_detected = sum(
        result.hidden_markers_exposed
        and not result.integrity_passes
        for result in contaminated_results
    )

    false_contamination_detections = sum(
        result.hidden_markers_exposed
        for result in clean_results
    )

    raw_expected_path_visible = (
        EVALUATOR_ONLY.expected_changed_files[0]
        in build_agent_payload(AGENT_VISIBLE)
    )

    namespaced_expected_path_visible = (
        EXPECTED_CHANGED_FILE_MARKERS[0]
        in build_agent_payload(AGENT_VISIBLE)
    )

    print("===== 011E BENCHMARK INTEGRITY =====")

    for result in results:
        print()
        print(f"[{result.condition}]")
        print(
            f"payload_constructed={result.payload_constructed}"
        )
        print(
            "hidden_markers_exposed="
            f"{result.hidden_markers_exposed}"
        )
        print(f"integrity_passes={result.integrity_passes}")
        print(f"exposed_markers={list(result.exposed_markers)}")
        print(f"matches_expected={result.matches_expected}")

    print()
    print("===== 011E EXPECTED-FILE NAMESPACE CHECK =====")
    print(
        "raw expected path visible as legitimate repository context: "
        f"{raw_expected_path_visible}"
    )
    print(
        "namespaced expected-file marker visible: "
        f"{namespaced_expected_path_visible}"
    )

    print()
    print("===== 011E AGGREGATE =====")
    print(
        "expected matrix matched: "
        f"{expected_matrix_matches}/{len(results)}"
    )
    print(
        f"clean payloads: {clean_payloads}/{len(results)}"
    )
    print(
        "contaminated payloads detected: "
        f"{contaminated_payloads_detected}/"
        f"{len(contaminated_results)}"
    )
    print(
        "false contamination detections on clean payload: "
        f"{false_contamination_detections}"
    )

    payload = {
        "experiment": "011E",
        "run": "run001",
        "kind": "deterministic_benchmark_integrity_validation",
        "agent_visible": asdict(AGENT_VISIBLE),
        "evaluator_only": asdict(EVALUATOR_ONLY),
        "hidden_markers": list(HIDDEN_MARKERS),
        "results": [
            asdict(result)
            for result in results
        ],
        "expected_file_namespace_check": {
            "raw_expected_path_visible": (
                raw_expected_path_visible
            ),
            "namespaced_expected_path_visible": (
                namespaced_expected_path_visible
            ),
        },
        "aggregate": {
            "conditions": len(results),
            "expected_matrix_matches": (
                expected_matrix_matches
            ),
            "clean_payloads": clean_payloads,
            "contaminated_payloads_detected": (
                contaminated_payloads_detected
            ),
            "contaminated_payloads_total": (
                len(contaminated_results)
            ),
            "false_contamination_detections": (
                false_contamination_detections
            ),
        },
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Wrote results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()