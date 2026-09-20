from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    record_id: str
    kind: str
    claim: str
    evidence_paths: tuple[str, ...]
    established_by_task: str
    repository_fingerprint: str


_MEMORY_BY_TASK: dict[
    str,
    tuple[MemoryRecord, ...],
] = {
    "config-001": (
        MemoryRecord(
            record_id="config-relationship-001",
            kind="relationship",
            claim=(
                "request_policy reads retry and timeout "
                "defaults from src/sample/settings.py."
            ),
            evidence_paths=(
                "src/sample/settings.py",
                "src/sample/client.py",
            ),
            established_by_task="config-001",
            repository_fingerprint="configuration-v1",
        ),
    ),
    "serialization-001": (
        MemoryRecord(
            record_id="serialization-relationship-001",
            kind="relationship",
            claim=(
                "serialize_user emits the external "
                "identifier key defined by the schema "
                "constant in src/sample/schema.py."
            ),
            evidence_paths=(
                "src/sample/schema.py",
                "src/sample/serializer.py",
            ),
            established_by_task="serialization-001",
            repository_fingerprint="serialization-v1",
        ),
    ),
    "parser-001": (
        MemoryRecord(
            record_id="parser-operational-001",
            kind="operational",
            claim=(
                "normalize_value strips surrounding "
                "whitespace before applying value "
                "normalization."
            ),
            evidence_paths=(
                "src/sample/parser.py",
            ),
            established_by_task="parser-001",
            repository_fingerprint="parser-v1",
        ),
    ),
}


_RELEVANT_MEMORY_BY_TASK: dict[
    str,
    frozenset[str],
] = {
    "config-002": frozenset(
        {
            "config-relationship-001",
        }
    ),
    "serialization-002": frozenset(
        {
            "serialization-relationship-001",
        }
    ),
    "parser-002": frozenset(
        {
            "parser-operational-001",
        }
    ),
}


def records_established_by(
    task_id: str,
) -> tuple[MemoryRecord, ...]:
    return _MEMORY_BY_TASK.get(
        task_id,
        (),
    )


def relevant_record_ids(
    task_id: str,
) -> frozenset[str]:
    return _RELEVANT_MEMORY_BY_TASK.get(
        task_id,
        frozenset(),
    )


def format_memory_records(
    records: tuple[MemoryRecord, ...],
) -> str:
    if not records:
        return ""

    sections = [
        (
            "Persistent repository memory\n\n"
            "The following records were established "
            "during earlier work in this repository. "
            "Treat them as supporting evidence only. "
            "Current repository contents and execution "
            "results take precedence if they conflict."
        )
    ]

    for record in records:
        evidence = "\n".join(
            f"- {path}"
            for path in record.evidence_paths
        )

        sections.append(
            
                f"[{record.kind}]\n"
                f"id: {record.record_id}\n"
                f"claim: {record.claim}\n"
                f"established_by: "
                f"{record.established_by_task}\n"
                "evidence:\n"
                f"{evidence}"
            
        )

    return "\n\n".join(sections)