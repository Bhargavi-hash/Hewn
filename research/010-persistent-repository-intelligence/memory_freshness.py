from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from memory_oracle import MemoryRecord


@dataclass(frozen=True, slots=True)
class EvidenceFingerprint:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class FingerprintedMemoryRecord:
    record: MemoryRecord
    evidence_fingerprints: tuple[
        EvidenceFingerprint,
        ...,
    ]


@dataclass(frozen=True, slots=True)
class FreshnessResult:
    record: FingerprintedMemoryRecord
    fresh: bool
    stale_paths: tuple[str, ...]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(65536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def fingerprint_record(
    *,
    repository_root: Path,
    record: MemoryRecord,
) -> FingerprintedMemoryRecord:
    fingerprints: list[
        EvidenceFingerprint
    ] = []

    for relative_path in record.evidence_paths:
        path = (
            repository_root
            / relative_path
        )

        if not path.is_file():
            raise FileNotFoundError(
                "Cannot establish memory from "
                "missing evidence file: "
                f"{relative_path}"
            )

        fingerprints.append(
            EvidenceFingerprint(
                path=relative_path,
                sha256=file_sha256(path),
            )
        )

    return FingerprintedMemoryRecord(
        record=record,
        evidence_fingerprints=tuple(
            fingerprints
        ),
    )


def check_freshness(
    *,
    repository_root: Path,
    record: FingerprintedMemoryRecord,
) -> FreshnessResult:
    stale_paths: list[str] = []

    for evidence in (
        record.evidence_fingerprints
    ):
        path = (
            repository_root
            / evidence.path
        )

        if not path.is_file():
            stale_paths.append(
                evidence.path
            )
            continue

        current_sha256 = file_sha256(
            path
        )

        if (
            current_sha256
            != evidence.sha256
        ):
            stale_paths.append(
                evidence.path
            )

    return FreshnessResult(
        record=record,
        fresh=not stale_paths,
        stale_paths=tuple(
            stale_paths
        ),
    )


def filter_fresh_records(
    *,
    repository_root: Path,
    records: tuple[
        FingerprintedMemoryRecord,
        ...,
    ],
) -> tuple[
    tuple[MemoryRecord, ...],
    tuple[FreshnessResult, ...],
]:
    results = tuple(
        check_freshness(
            repository_root=(
                repository_root
            ),
            record=record,
        )
        for record in records
    )

    fresh = tuple(
        result.record.record
        for result in results
        if result.fresh
    )

    return fresh, results