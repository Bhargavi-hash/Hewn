from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_FAILED_TEST_RE = re.compile(
    r"^FAILED\s+(?P<test>\S+)(?:\s+-\s+(?P<summary>.*))?$"
)

_PASSED_COUNT_RE = re.compile(r"(?P<count>\d+)\s+passed\b")
_FAILED_COUNT_RE = re.compile(r"(?P<count>\d+)\s+failed\b")
_ERROR_COUNT_RE = re.compile(r"(?P<count>\d+)\s+error(?:s)?\b")

_LOCATION_RE = re.compile(
    r"^(?P<path>[^:\s]+\.py):(?P<line>\d+):"
)

_EXCEPTION_RE = re.compile(
    r"^E\s+(?P<exception>[A-Za-z_][A-Za-z0-9_.]*):\s*(?P<message>.*)$"
)

_ASSERTION_RE = re.compile(
    r"^E\s+(?P<assertion>assert\b.*)$"
)


@dataclass(frozen=True)
class FailureEvidence:
    test: str
    exception: str | None = None
    message: str | None = None
    assertion: str | None = None
    location: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {"test": self.test}

        if self.exception is not None:
            result["exception"] = self.exception

        if self.message is not None:
            result["message"] = self.message

        if self.assertion is not None:
            result["assertion"] = self.assertion

        if self.location is not None:
            result["location"] = self.location

        return result


def _summary_count(
    pattern: re.Pattern[str],
    text: str,
) -> int:
    matches = list(pattern.finditer(text))
    if not matches:
        return 0

    return int(matches[-1].group("count"))


def _failure_sections(lines: list[str]) -> list[list[str]]:
    starts: list[int] = []

    for index, line in enumerate(lines):
        if line.startswith("_") and " test_" in line:
            starts.append(index)

    sections: list[list[str]] = []

    for position, start in enumerate(starts):
        end = (
            starts[position + 1]
            if position + 1 < len(starts)
            else len(lines)
        )
        sections.append(lines[start:end])

    return sections


def _test_name_from_section(
    section: list[str],
) -> str | None:
    if not section:
        return None

    heading = section[0].strip("_ ")
    if heading.startswith("test_"):
        return heading

    return None


def _location_from_section(
    section: list[str],
) -> str | None:
    candidates: list[str] = []

    for line in section:
        stripped = line.strip()
        match = _LOCATION_RE.match(stripped)
        if match is None:
            continue

        candidates.append(
            f"{match.group('path')}:{match.group('line')}"
        )

    if not candidates:
        return None

    return candidates[-1]


def _exception_from_section(
    section: list[str],
) -> tuple[str | None, str | None]:
    for line in reversed(section):
        stripped = line.strip()
        match = _EXCEPTION_RE.match(stripped)
        if match is None:
            continue

        return (
            match.group("exception"),
            match.group("message"),
        )

    return None, None


def _assertion_from_section(
    section: list[str],
) -> str | None:
    for line in section:
        stripped = line.strip()
        match = _ASSERTION_RE.match(stripped)
        if match is not None:
            return match.group("assertion")

    return None


def _short_summary_failures(
    lines: list[str],
) -> list[tuple[str, str | None]]:
    failures: list[tuple[str, str | None]] = []

    for line in lines:
        match = _FAILED_TEST_RE.match(line.strip())
        if match is None:
            continue

        failures.append(
            (
                match.group("test"),
                match.group("summary"),
            )
        )

    return failures


def normalize_pytest_output(
    raw_output: str,
) -> dict[str, Any]:
    lines = raw_output.splitlines()
    sections = _failure_sections(lines)
    summary_failures = _short_summary_failures(lines)

    section_by_name: dict[str, list[str]] = {}

    for section in sections:
        test_name = _test_name_from_section(section)
        if test_name is not None:
            section_by_name[test_name] = section

    failures: list[FailureEvidence] = []

    for full_test_name, short_summary in summary_failures:
        simple_name = full_test_name.rsplit("::", maxsplit=1)[-1]
        section = section_by_name.get(simple_name, [])

        exception, message = _exception_from_section(section)
        assertion = _assertion_from_section(section)
        location = _location_from_section(section)

        if (
            exception is None
            and short_summary
            and ":" in short_summary
        ):
            possible_exception, possible_message = (
                short_summary.split(":", maxsplit=1)
            )
            possible_exception = possible_exception.strip()
        
            if re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_.]*",
                possible_exception,
            ):
                exception = possible_exception
                message = possible_message.strip()

        if assertion is not None and exception is None:
            exception = "AssertionError"

        failures.append(
            FailureEvidence(
                test=full_test_name,
                exception=exception,
                message=message,
                assertion=assertion,
                location=location,
            )
        )

    failed = _summary_count(_FAILED_COUNT_RE, raw_output)
    passed = _summary_count(_PASSED_COUNT_RE, raw_output)
    errors = _summary_count(_ERROR_COUNT_RE, raw_output)

    return {
        "verification": "failed",
        "tool": "pytest",
        "failed_checks": [
            failure.as_dict()
            for failure in failures
        ],
        "summary": {
            "failed": failed,
            "passed": passed,
            "errors": errors,
        },
    }