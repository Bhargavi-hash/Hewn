from __future__ import annotations

import pytest
from grounding import extract_structure, format_structure
from planning import PlanningProtocolError, parse_plan


def test_parse_valid_plan() -> None:
    plan = parse_plan(
        """
        {
          "files": [
            {
              "path": "src/a.py",
              "symbols": ["run"],
              "operations": ["update run behavior"]
            }
          ],
          "verification": ["tests/test_a.py"]
        }
        """
    )

    assert plan.files[0].path == "src/a.py"
    assert plan.files[0].symbols == ("run",)
    assert plan.verification == ("tests/test_a.py",)


def test_reject_markdown_fence() -> None:
    with pytest.raises(PlanningProtocolError):
        parse_plan(
            "```json\n"
            '{"files": [], "verification": []}'
            "\n```"
        )


def test_reject_extra_top_level_field() -> None:
    with pytest.raises(PlanningProtocolError):
        parse_plan(
            """
            {
              "files": [
                {
                  "path": "src/a.py",
                  "symbols": [],
                  "operations": ["change behavior"]
                }
              ],
              "verification": ["tests/test_a.py"],
              "reason": "because"
            }
            """
        )


def test_reject_duplicate_file() -> None:
    with pytest.raises(PlanningProtocolError):
        parse_plan(
            """
            {
              "files": [
                {
                  "path": "src/a.py",
                  "symbols": [],
                  "operations": ["first"]
                },
                {
                  "path": "src/a.py",
                  "symbols": [],
                  "operations": ["second"]
                }
              ],
              "verification": ["tests/test_a.py"]
            }
            """
        )


def test_structure_is_mechanical() -> None:
    structures = extract_structure(
        {
            "src/a.py": (
                "from config import TIMEOUT\n\n"
                "VALUE = 3\n\n"
                "def run() -> int:\n"
                "    return VALUE\n"
            )
        }
    )

    assert len(structures) == 1
    assert structures[0].path == "src/a.py"
    assert structures[0].symbols == (
        "VALUE",
        "run",
    )
    assert structures[0].imports == (
        "config: TIMEOUT",
    )


def test_format_structure() -> None:
    structures = extract_structure(
        {
            "src/a.py": (
                "VALUE = 3\n\n"
                "def run() -> int:\n"
                "    return VALUE\n"
            )
        }
    )

    rendered = format_structure(structures)

    assert "src/a.py" in rendered
    assert "VALUE, run" in rendered