from __future__ import annotations

import ast
import json
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = MODULE_ROOT / "results"
OUTPUT_PATH = (
    RESULTS_ROOT
    / "010d-memory-value-run001.json"
)


@dataclass(frozen=True, slots=True)
class MemoryValueCase:
    case_id: str
    memory_class: str
    expected_fact: str
    historical_information_required: bool
    setup: Callable[[Path], None]
    reconstruct: Callable[[Path], tuple[bool, tuple[str, ...]]]


@dataclass(frozen=True, slots=True)
class MemoryValueResult:
    case_id: str
    memory_class: str
    expected_fact: str

    reconstructible_from_current_state: bool
    reconstruction_evidence: tuple[str, ...]

    historical_information_required: bool
    current_state_provenance_available: bool
    persistence_candidate: bool


def write_file(
    root: Path,
    relative_path: str,
    text: str,
) -> None:
    path = root / relative_path
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        text,
        encoding="utf-8",
    )


def setup_structural(
    root: Path,
) -> None:
    write_file(
        root,
        "src/sample/client.py",
        (
            "from sample.settings import RETRY_COUNT\n\n"
            "def request_policy() -> int:\n"
            "    return RETRY_COUNT\n"
        ),
    )

    write_file(
        root,
        "src/sample/settings.py",
        "RETRY_COUNT = 4\n",
    )


def reconstruct_structural(
    root: Path,
) -> tuple[bool, tuple[str, ...]]:
    target = (
        root / "src/sample/client.py"
    )

    tree = ast.parse(
        target.read_text(
            encoding="utf-8"
        )
    )

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        if node.module != "sample.settings":
            continue

        imported = {
            alias.name
            for alias in node.names
        }

        if "RETRY_COUNT" in imported:
            return (
                True,
                (
                    (
                        "src/sample/client.py imports "
                        "RETRY_COUNT from sample.settings"
                    ),
                ),
            )

    return False, ()


def setup_architectural(
    root: Path,
) -> None:
    write_file(
        root,
        "src/sample/service.py",
        (
            "from sample.repository import load_user\n\n"
            "def get_user(user_id: int) -> dict[str, object]:\n"
            "    return load_user(user_id)\n"
        ),
    )

    write_file(
        root,
        "src/sample/repository.py",
        (
            "def load_user(user_id: int) -> dict[str, object]:\n"
            "    return {'id': user_id}\n"
        ),
    )


def reconstruct_architectural(
    root: Path,
) -> tuple[bool, tuple[str, ...]]:
    service = (
        root / "src/sample/service.py"
    )

    text = service.read_text(
        encoding="utf-8"
    )

    evidence = (
        (
            "src/sample/service.py currently calls "
            "sample.repository.load_user"
        ),
    )

    # The current source shows the dependency, but not the
    # historical rationale that direct storage access was
    # intentionally rejected to preserve the service/repository
    # boundary.
    if (
        "from sample.repository import load_user"
        in text
    ):
        return False, evidence

    return False, ()


def setup_operational(
    root: Path,
) -> None:
    write_file(
        root,
        "pyproject.toml",
        (
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests"]\n'
        ),
    )

    write_file(
        root,
        "tests/test_sample.py",
        (
            "def test_sample() -> None:\n"
            "    assert True\n"
        ),
    )


def reconstruct_operational(
    root: Path,
) -> tuple[bool, tuple[str, ...]]:
    pyproject = (
        root / "pyproject.toml"
    )

    text = pyproject.read_text(
        encoding="utf-8"
    )

    if 'testpaths = ["tests"]' in text:
        return (
            True,
            (
                (
                    "pyproject.toml declares pytest "
                    "testpaths=tests"
                ),
            ),
        )

    return False, ()


def setup_historical_failure(
    root: Path,
) -> None:
    # This is the repository after the historical failure
    # has already been fixed.
    write_file(
        root,
        "src/sample/parser.py",
        (
            "def normalize_value(value: str) -> str:\n"
            "    return value.strip().lower()\n"
        ),
    )

    write_file(
        root,
        "tests/test_parser.py",
        (
            "from sample.parser import normalize_value\n\n"
            "def test_normalize_value() -> None:\n"
            "    assert normalize_value(' Alpha ') == 'alpha'\n"
        ),
    )


def reconstruct_historical_failure(
    root: Path,
) -> tuple[bool, tuple[str, ...]]:
    parser = (
        root / "src/sample/parser.py"
    )

    text = parser.read_text(
        encoding="utf-8"
    )

    evidence = (
        (
            "current parser contains the corrected "
            "strip-and-lower implementation"
        ),
    )

    # Current state can show the fix but cannot establish
    # that a prior implementation failed because it omitted
    # lowercasing.
    if ".strip().lower()" in text:
        return False, evidence

    return False, ()


def setup_decision(
    root: Path,
) -> None:
    write_file(
        root,
        "src/sample/cache.py",
        (
            "class InMemoryCache:\n"
            "    def __init__(self) -> None:\n"
            "        self._values: dict[str, str] = {}\n"
        ),
    )


def reconstruct_decision(
    root: Path,
) -> tuple[bool, tuple[str, ...]]:
    cache = (
        root / "src/sample/cache.py"
    )

    text = cache.read_text(
        encoding="utf-8"
    )

    evidence = (
        (
            "src/sample/cache.py currently implements "
            "an in-memory cache"
        ),
    )

    # Current source establishes the chosen implementation,
    # but not that Redis was considered and rejected because
    # the project intentionally avoids an external runtime
    # dependency.
    if "class InMemoryCache" in text:
        return False, evidence

    return False, ()


CASES = (
    MemoryValueCase(
        case_id="structural-001",
        memory_class="structural",
        expected_fact=(
            "request_policy depends on RETRY_COUNT "
            "from sample.settings"
        ),
        historical_information_required=False,
        setup=setup_structural,
        reconstruct=reconstruct_structural,
    ),
    MemoryValueCase(
        case_id="architectural-001",
        memory_class="architectural",
        expected_fact=(
            "direct storage access was rejected to "
            "preserve the service/repository boundary"
        ),
        historical_information_required=True,
        setup=setup_architectural,
        reconstruct=reconstruct_architectural,
    ),
    MemoryValueCase(
        case_id="operational-001",
        memory_class="operational",
        expected_fact=(
            "the repository's pytest suite is rooted "
            "under tests/"
        ),
        historical_information_required=False,
        setup=setup_operational,
        reconstruct=reconstruct_operational,
    ),
    MemoryValueCase(
        case_id="historical-failure-001",
        memory_class="historical_failure",
        expected_fact=(
            "a previous parser implementation failed "
            "because it stripped whitespace but did "
            "not lowercase values"
        ),
        historical_information_required=True,
        setup=setup_historical_failure,
        reconstruct=reconstruct_historical_failure,
    ),
    MemoryValueCase(
        case_id="decision-001",
        memory_class="decision",
        expected_fact=(
            "Redis was rejected because the project "
            "intentionally avoids an external runtime "
            "dependency for this cache"
        ),
        historical_information_required=True,
        setup=setup_decision,
        reconstruct=reconstruct_decision,
    ),
)


def evaluate_case(
    case: MemoryValueCase,
) -> MemoryValueResult:
    with tempfile.TemporaryDirectory(
        prefix=f"hewn-010d-{case.case_id}-"
    ) as temporary:
        root = Path(temporary) / "repo"
        root.mkdir()

        case.setup(root)

        reconstructible, evidence = (
            case.reconstruct(root)
        )

        current_state_provenance_available = bool(
            evidence
        )

        persistence_candidate = (
            not reconstructible
            and case.historical_information_required
        )

        return MemoryValueResult(
            case_id=case.case_id,
            memory_class=case.memory_class,
            expected_fact=case.expected_fact,
            reconstructible_from_current_state=(
                reconstructible
            ),
            reconstruction_evidence=evidence,
            historical_information_required=(
                case.historical_information_required
            ),
            current_state_provenance_available=(
                current_state_provenance_available
            ),
            persistence_candidate=(
                persistence_candidate
            ),
        )


def validate_result(
    result: MemoryValueResult,
) -> None:
    if (
        result.reconstructible_from_current_state
        and result.historical_information_required
    ):
        raise AssertionError(
            f"{result.case_id}: historical-only fact "
            "was unexpectedly reconstructed"
        )

    if (
        result.persistence_candidate
        and not result.historical_information_required
    ):
        raise AssertionError(
            f"{result.case_id}: non-historical fact "
            "was incorrectly promoted"
        )


def print_summary(
    results: list[MemoryValueResult],
) -> None:
    print("\n===== 010D SUMMARY =====")

    reconstructible = 0
    non_reconstructible = 0
    candidates = 0

    for result in results:
        reconstructible += int(
            result.reconstructible_from_current_state
        )

        non_reconstructible += int(
            not result.reconstructible_from_current_state
        )

        candidates += int(
            result.persistence_candidate
        )

        print(
            f"\n[{result.case_id}]"
        )

        print(
            f"class={result.memory_class}"
        )

        print(
            "reconstructible="
            f"{result.reconstructible_from_current_state}"
        )

        print(
            "historical_required="
            f"{result.historical_information_required}"
        )

        print(
            "current_provenance="
            f"{result.current_state_provenance_available}"
        )

        print(
            "persistence_candidate="
            f"{result.persistence_candidate}"
        )

        print(
            "evidence="
            f"{list(result.reconstruction_evidence)}"
        )

    print("\n===== 010D AGGREGATE =====")

    print(
        "reconstructible from current state: "
        f"{reconstructible}/{len(results)}"
    )

    print(
        "not reconstructible from current state: "
        f"{non_reconstructible}/{len(results)}"
    )

    print(
        "persistence candidates: "
        f"{candidates}/{len(results)}"
    )


def main() -> None:
    results = [
        evaluate_case(case)
        for case in CASES
    ]

    for result in results:
        validate_result(result)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "experiment": "010D",
        "run": "run001",
        "model_invoked": False,
        "question": (
            "Which repository knowledge classes "
            "contain information not recoverable "
            "from current repository state?"
        ),
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