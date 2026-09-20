from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from memory_freshness import (
    FingerprintedMemoryRecord,
    filter_fresh_records,
    fingerprint_record,
)
from memory_oracle import (
    MemoryRecord,
    format_memory_records,
    records_established_by,
)

MODULE_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = MODULE_ROOT / "fixtures"
RESULTS_ROOT = MODULE_ROOT / "results"

OUTPUT_PATH = (
    RESULTS_ROOT
    / "010c-stale-memory-run001.json"
)


@dataclass(frozen=True, slots=True)
class StaleCase:
    pair_id: str
    task_1_id: str
    changed_path: str
    mutate: Callable[[Path], None]


@dataclass(frozen=True, slots=True)
class ConditionResult:
    pair_id: str
    condition: str

    records_available: int
    fresh_records: int
    stale_records: int
    stale_records_rejected: int
    stale_records_reaching_context: int

    stale_paths: tuple[str, ...]

    memory_character_count: int

    current_evidence_expected: tuple[
        str,
        ...,
    ]
    current_evidence_preserved: bool


@dataclass(frozen=True, slots=True)
class CaseResult:
    pair_id: str
    no_freshness: ConditionResult
    freshness: ConditionResult
    freshness_with_current_evidence: (
        ConditionResult
    )


def replace_once(
    *,
    path: Path,
    old: str,
    new: str,
) -> None:
    original = path.read_text(
        encoding="utf-8"
    )

    count = original.count(old)

    if count != 1:
        raise ValueError(
            f"Expected exactly one occurrence "
            f"of {old!r} in {path}, "
            f"found {count}"
        )

    path.write_text(
        original.replace(
            old,
            new,
            1,
        ),
        encoding="utf-8",
    )


def mutate_configuration(
    root: Path,
) -> None:
    path = (
        root
        / "src/sample/settings.py"
    )

    original = path.read_text(
        encoding="utf-8"
    )

    replacements = (
        ("RETRY_COUNT = 2", "RETRY_COUNT = 4"),
        ("RETRY_COUNT = 4", "RETRY_COUNT = 6"),
    )

    for old, new in replacements:
        if old in original:
            replace_once(
                path=path,
                old=old,
                new=new,
            )
            return

    raise ValueError(
        "Could not locate configuration "
        "mutation target"
    )


def mutate_serialization(
    root: Path,
) -> None:
    path = (
        root
        / "src/sample/schema.py"
    )

    original = path.read_text(
        encoding="utf-8"
    )

    candidates = (
        (
            'USER_ID_FIELD = "user_id"',
            'USER_ID_FIELD = "account_id"',
        ),
        (
            'ACCOUNT_ID_FIELD = "account_id"',
            'ACCOUNT_ID_FIELD = "member_id"',
        ),
    )

    for old, new in candidates:
        if old in original:
            replace_once(
                path=path,
                old=old,
                new=new,
            )
            return

    raise ValueError(
        "Could not locate serialization "
        "mutation target"
    )


def mutate_parser(
    root: Path,
) -> None:
    path = (
        root
        / "src/sample/parser.py"
    )

    original = path.read_text(
        encoding="utf-8"
    )

    candidates = (
        (
            "return value.strip()",
            "return value.strip().lower()",
        ),
        (
            "return value.strip().lower()",
            (
                "normalized = "
                "value.strip().lower()\n"
                "    return normalized or None"
            ),
        ),
    )

    for old, new in candidates:
        if old in original:
            replace_once(
                path=path,
                old=old,
                new=new,
            )
            return

    raise ValueError(
        "Could not locate parser "
        "mutation target"
    )


CASES = (
    StaleCase(
        pair_id="configuration",
        task_1_id="config-001",
        changed_path=(
            "src/sample/settings.py"
        ),
        mutate=mutate_configuration,
    ),
    StaleCase(
        pair_id="serialization",
        task_1_id=(
            "serialization-001"
        ),
        changed_path=(
            "src/sample/schema.py"
        ),
        mutate=mutate_serialization,
    ),
    StaleCase(
        pair_id="parser",
        task_1_id="parser-001",
        changed_path=(
            "src/sample/parser.py"
        ),
        mutate=mutate_parser,
    ),
)


def locate_fixture(
    pair_id: str,
) -> Path:
    candidates = [
        path
        for path in FIXTURES_ROOT.iterdir()
        if (
            path.is_dir()
            and pair_id
            in path.name
        )
    ]

    if len(candidates) != 1:
        raise ValueError(
            "Expected exactly one fixture "
            f"for {pair_id}, found "
            f"{len(candidates)}: "
            f"{[path.name for path in candidates]}"
        )

    return candidates[0]


def establish_records(
    *,
    root: Path,
    task_1_id: str,
) -> tuple[
    FingerprintedMemoryRecord,
    ...,
]:
    records = records_established_by(
        task_1_id
    )

    if not records:
        raise ValueError(
            "No memory records for "
            f"{task_1_id}"
        )

    return tuple(
        fingerprint_record(
            repository_root=root,
            record=record,
        )
        for record in records
    )


def raw_records(
    records: tuple[
        FingerprintedMemoryRecord,
        ...,
    ],
) -> tuple[MemoryRecord, ...]:
    return tuple(
        record.record
        for record in records
    )


def evaluate_no_freshness(
    *,
    case: StaleCase,
    records: tuple[
        FingerprintedMemoryRecord,
        ...,
    ],
) -> ConditionResult:
    supplied = raw_records(records)

    memory_text = (
        format_memory_records(
            supplied
        )
    )

    return ConditionResult(
        pair_id=case.pair_id,
        condition="no_freshness",
        records_available=len(records),
        fresh_records=0,
        stale_records=len(records),
        stale_records_rejected=0,
        stale_records_reaching_context=(
            len(supplied)
        ),
        stale_paths=(
            case.changed_path,
        ),
        memory_character_count=len(
            memory_text
        ),
        current_evidence_expected=(),
        current_evidence_preserved=True,
    )


def evaluate_freshness(
    *,
    root: Path,
    case: StaleCase,
    records: tuple[
        FingerprintedMemoryRecord,
        ...,
    ],
    preserve_current_evidence: bool,
) -> ConditionResult:
    fresh, freshness_results = (
        filter_fresh_records(
            repository_root=root,
            records=records,
        )
    )

    stale_results = tuple(
        result
        for result
        in freshness_results
        if not result.fresh
    )

    stale_paths = tuple(
        sorted(
            {
                path
                for result
                in stale_results
                for path
                in result.stale_paths
            }
        )
    )

    memory_text = (
        format_memory_records(
            fresh
        )
    )

    expected_current = (
        (case.changed_path,)
        if preserve_current_evidence
        else ()
    )

    # 010C tests that memory invalidation does not
    # remove or suppress independently available
    # current repository evidence. The changed file
    # itself is current evidence for this deterministic
    # diagnostic.
    preserved = all(
        (root / path).is_file()
        for path in expected_current
    )

    return ConditionResult(
        pair_id=case.pair_id,
        condition=(
            "freshness_with_current_evidence"
            if preserve_current_evidence
            else "freshness"
        ),
        records_available=len(records),
        fresh_records=len(fresh),
        stale_records=len(
            stale_results
        ),
        stale_records_rejected=len(
            stale_results
        ),
        stale_records_reaching_context=0,
        stale_paths=stale_paths,
        memory_character_count=len(
            memory_text
        ),
        current_evidence_expected=(
            expected_current
        ),
        current_evidence_preserved=(
            preserved
        ),
    )


def evaluate_case(
    case: StaleCase,
) -> CaseResult:
    fixture = locate_fixture(
        case.pair_id
    )

    with tempfile.TemporaryDirectory(
        prefix=(
            f"hewn-010c-"
            f"{case.pair_id}-"
        )
    ) as temporary:
        root = (
            Path(temporary) / "repo"
        )

        shutil.copytree(
            fixture,
            root,
        )

        records = establish_records(
            root=root,
            task_1_id=case.task_1_id,
        )

        case.mutate(root)

        no_freshness = (
            evaluate_no_freshness(
                case=case,
                records=records,
            )
        )

        freshness = (
            evaluate_freshness(
                root=root,
                case=case,
                records=records,
                preserve_current_evidence=False,
            )
        )

        with_current = (
            evaluate_freshness(
                root=root,
                case=case,
                records=records,
                preserve_current_evidence=True,
            )
        )

        return CaseResult(
            pair_id=case.pair_id,
            no_freshness=no_freshness,
            freshness=freshness,
            freshness_with_current_evidence=(
                with_current
            ),
        )


def validate_case(
    result: CaseResult,
) -> None:
    baseline = result.no_freshness
    freshness = result.freshness
    current = (
        result
        .freshness_with_current_evidence
    )

    if (
        baseline
        .stale_records_reaching_context
        != baseline.records_available
    ):
        raise AssertionError(
            f"{result.pair_id}: "
            "no-freshness condition did not "
            "expose every stale record"
        )

    if (
        freshness
        .stale_records_rejected
        != freshness.records_available
    ):
        raise AssertionError(
            f"{result.pair_id}: "
            "freshness condition did not "
            "reject every stale record"
        )

    if (
        freshness
        .stale_records_reaching_context
        != 0
    ):
        raise AssertionError(
            f"{result.pair_id}: "
            "stale memory reached context"
        )

    if (
        current
        .stale_records_reaching_context
        != 0
    ):
        raise AssertionError(
            f"{result.pair_id}: "
            "stale memory reached context "
            "with current evidence"
        )

    if not (
        current
        .current_evidence_preserved
    ):
        raise AssertionError(
            f"{result.pair_id}: "
            "current evidence was not "
            "preserved"
        )


def print_summary(
    results: list[CaseResult],
) -> None:
    print(
        "\n===== 010C SUMMARY ====="
    )

    total_stale = 0
    total_rejected = 0
    total_baseline_exposed = 0
    current_preserved = 0

    for result in results:
        baseline = result.no_freshness
        freshness = result.freshness
        current = (
            result
            .freshness_with_current_evidence
        )

        total_stale += (
            freshness.stale_records
        )

        total_rejected += (
            freshness
            .stale_records_rejected
        )

        total_baseline_exposed += (
            baseline
            .stale_records_reaching_context
        )

        current_preserved += int(
            current
            .current_evidence_preserved
        )

        print(
            f"\n[{result.pair_id}]"
        )

        print(
            "no_freshness: "
            f"stale_reaching_context="
            f"{baseline.stale_records_reaching_context} "
            f"memory_chars="
            f"{baseline.memory_character_count}"
        )

        print(
            "freshness: "
            f"stale={freshness.stale_records} "
            f"rejected="
            f"{freshness.stale_records_rejected} "
            f"reaching_context="
            f"{freshness.stale_records_reaching_context} "
            f"stale_paths="
            f"{list(freshness.stale_paths)}"
        )

        print(
            "freshness_with_current_evidence: "
            f"reaching_context="
            f"{current.stale_records_reaching_context} "
            f"current_preserved="
            f"{current.current_evidence_preserved}"
        )

    print(
        "\n===== 010C AGGREGATE ====="
    )

    print(
        "baseline stale records exposed: "
        f"{total_baseline_exposed}/"
        f"{total_stale}"
    )

    print(
        "stale records rejected: "
        f"{total_rejected}/"
        f"{total_stale}"
    )

    print(
        "current evidence preserved: "
        f"{current_preserved}/"
        f"{len(results)}"
    )


def main() -> None:
    results = [
        evaluate_case(case)
        for case in CASES
    ]

    for result in results:
        validate_case(result)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "experiment": "010C",
        "run": "run001",
        "mechanism": (
            "SHA-256 provenance-file "
            "content invalidation"
        ),
        "model_invoked": False,
        "results": [
            asdict(result)
            for result in results
        ],
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print_summary(results)

    print(
        "\nWrote results to "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()