from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileSpec:
    path: str
    buggy: str
    fixed: str | None = None


@dataclass(frozen=True)
class FixtureSpec:
    name: str
    files: tuple[FileSpec, ...]
    visible_tests: str
    hidden_tests: str


def unchanged(path: str, content: str) -> FileSpec:
    return FileSpec(path=path, buggy=content)


FIXTURES = (
    FixtureSpec(
        name="localized_001",
        files=(
            FileSpec(
                "src/sample/slug.py",
                """\
import re


def make_slug(value: str) -> str:
    value = value.lower()
    return re.sub(r"[^a-z0-9]+", "-", value)
""",
                """\
import re


def make_slug(value: str) -> str:
    value = value.lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.slug import make_slug


def test_slug_words() -> None:
    assert make_slug("Hello World") == "hello-world"
""",
        hidden_tests="""\
from sample.slug import make_slug


def test_surrounding_punctuation() -> None:
    assert make_slug("  Hello World!!  ") == "hello-world"


def test_only_punctuation() -> None:
    assert make_slug("!!!") == ""
""",
    ),
    FixtureSpec(
        name="localized_002",
        files=(
            FileSpec(
                "src/sample/numbers.py",
                """\
def clamp(value: int, lower: int, upper: int) -> int:
    if value < lower:
        return upper
    if value > upper:
        return upper
    return value
""",
                """\
def clamp(value: int, lower: int, upper: int) -> int:
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.numbers import clamp


def test_inside_range() -> None:
    assert clamp(5, 0, 10) == 5


def test_upper_boundary() -> None:
    assert clamp(15, 0, 10) == 10
""",
        hidden_tests="""\
from sample.numbers import clamp


def test_below_range() -> None:
    assert clamp(-4, 0, 10) == 0
""",
    ),
    FixtureSpec(
        name="localized_003",
        files=(
            FileSpec(
                "src/sample/users.py",
                """\
def normalize_username(value: str) -> str:
    return value.lower()
""",
                """\
def normalize_username(value: str) -> str:
    return value.strip().lower()
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.users import normalize_username


def test_lowercase() -> None:
    assert normalize_username("Alice") == "alice"
""",
        hidden_tests="""\
from sample.users import normalize_username


def test_surrounding_whitespace() -> None:
    assert normalize_username("  Alice  ") == "alice"
""",
    ),
    FixtureSpec(
        name="cross_file_001",
        files=(
            unchanged(
                "src/shop/checkout.py",
                """\
from shop.discounts import apply_percentage_discount


def checkout_total(subtotal: float, percent: float) -> float:
    return apply_percentage_discount(subtotal, percent)
""",
            ),
            FileSpec(
                "src/shop/discounts.py",
                """\
def apply_percentage_discount(
    subtotal: float,
    percent: float,
) -> float:
    return subtotal - percent
""",
                """\
def apply_percentage_discount(
    subtotal: float,
    percent: float,
) -> float:
    return subtotal * (1 - percent / 100)
""",
            ),
            unchanged("src/shop/__init__.py", ""),
        ),
        visible_tests="""\
from shop.checkout import checkout_total


def test_no_discount() -> None:
    assert checkout_total(100.0, 0.0) == 100.0
""",
        hidden_tests="""\
from shop.checkout import checkout_total


def test_percentage_discount() -> None:
    assert checkout_total(200.0, 25.0) == 150.0
""",
    ),
    FixtureSpec(
        name="cross_file_002",
        files=(
            unchanged(
                "src/app/render.py",
                """\
from app.profile import Profile


def render_greeting(profile: Profile) -> str:
    return f"Hello, {profile.greeting_name()}!"
""",
            ),
            FileSpec(
                "src/app/profile.py",
                """\
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    account_id: str
    display_name: str

    def greeting_name(self) -> str:
        return self.account_id
""",
                """\
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    account_id: str
    display_name: str

    def greeting_name(self) -> str:
        return self.display_name
""",
            ),
            unchanged("src/app/__init__.py", ""),
        ),
        visible_tests="""\
from app.profile import Profile
from app.render import render_greeting


def test_greeting_shape() -> None:
    profile = Profile("alice", "alice")
    assert render_greeting(profile) == "Hello, alice!"
""",
        hidden_tests="""\
from app.profile import Profile
from app.render import render_greeting


def test_display_name_is_used() -> None:
    profile = Profile("acct-481", "Alice")
    assert render_greeting(profile) == "Hello, Alice!"
""",
    ),
    FixtureSpec(
        name="cross_file_003",
        files=(
            unchanged(
                "src/reporting/summary.py",
                """\
from reporting.records import active_records


def active_count(records: list[dict[str, object]]) -> int:
    return len(active_records(records))
""",
            ),
            FileSpec(
                "src/reporting/records.py",
                """\
def active_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    return records
""",
                """\
def active_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        record
        for record in records
        if record.get("enabled") is True
    ]
""",
            ),
            unchanged("src/reporting/__init__.py", ""),
        ),
        visible_tests="""\
from reporting.summary import active_count


def test_all_active() -> None:
    records = [
        {"id": 1, "enabled": True},
        {"id": 2, "enabled": True},
    ]
    assert active_count(records) == 2
""",
        hidden_tests="""\
from reporting.summary import active_count


def test_disabled_records_are_excluded() -> None:
    records = [
        {"id": 1, "enabled": True},
        {"id": 2, "enabled": False},
        {"id": 3, "enabled": True},
    ]
    assert active_count(records) == 2
""",
    ),
    FixtureSpec(
        name="test_driven_001",
        files=(
            FileSpec(
                "src/sample/paths.py",
                """\
def join_path(parent: str, child: str) -> str:
    return parent + "/" + child
""",
                """\
def join_path(parent: str, child: str) -> str:
    return parent.rstrip("/") + "/" + child.lstrip("/")
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.paths import join_path


def test_join_avoids_duplicate_separator() -> None:
    assert join_path("/tmp/", "/report.txt") == "/tmp/report.txt"
""",
        hidden_tests="""\
from sample.paths import join_path


def test_parent_with_trailing_separator() -> None:
    assert join_path("/var/log/", "app.log") == "/var/log/app.log"


def test_child_with_leading_separator() -> None:
    assert join_path("/var/log", "/app.log") == "/var/log/app.log"
""",
    ),
    FixtureSpec(
        name="test_driven_002",
        files=(
            FileSpec(
                "src/sample/tags.py",
                """\
def unique_tags(tags: list[str]) -> list[str]:
    return tags
""",
                """\
def unique_tags(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(tags))
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.tags import unique_tags


def test_duplicate_tags_are_removed() -> None:
    assert unique_tags(["python", "agent", "python"]) == [
        "python",
        "agent",
    ]
""",
        hidden_tests="""\
from sample.tags import unique_tags


def test_original_order_is_preserved() -> None:
    assert unique_tags(["b", "a", "b", "c", "a"]) == [
        "b",
        "a",
        "c",
    ]
""",
    ),
    FixtureSpec(
        name="test_driven_003",
        files=(
            FileSpec(
                "src/sample/titles.py",
                """\
def format_title(title: str) -> str:
    return title.strip().title() + " | Hewn"
""",
                """\
def format_title(title: str) -> str:
    normalized = title.strip()
    if not normalized:
        return "Hewn"
    return normalized.title() + " | Hewn"
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.titles import format_title


def test_empty_title() -> None:
    assert format_title("   ") == "Hewn"
""",
        hidden_tests="""\
from sample.titles import format_title


def test_empty_string() -> None:
    assert format_title("") == "Hewn"


def test_whitespace_only_title() -> None:
    assert format_title("\t  ") == "Hewn"
""",
    ),
    FixtureSpec(
        name="verification_001",
        files=(
            FileSpec(
                "src/sample/boolean.py",
                """\
def parse_bool(value: str) -> bool:
    return bool(value)
""",
                """\
def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.boolean import parse_bool


def test_true() -> None:
    assert parse_bool("true") is True
""",
        hidden_tests="""\
from sample.boolean import parse_bool


def test_false() -> None:
    assert parse_bool("false") is False


def test_surrounding_whitespace() -> None:
    assert parse_bool(" YES ") is True
""",
    ),
    FixtureSpec(
        name="verification_002",
        files=(
            FileSpec(
                "src/sample/retry.py",
                """\
def retry_delay(base: int, attempt: int) -> int:
    return base * attempt
""",
                """\
def retry_delay(base: int, attempt: int) -> int:
    return base * (2 ** attempt)
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.retry import retry_delay


def test_zero_base_stays_zero() -> None:
    assert retry_delay(0, 3) == 0
""",
        hidden_tests="""\
from sample.retry import retry_delay


def test_exponential_delay() -> None:
    assert retry_delay(2, 3) == 16
""",
    ),
    FixtureSpec(
        name="verification_003",
        files=(
            FileSpec(
                "src/sample/files.py",
                """\
def extension(filename: str) -> str:
    return filename.split(".")[1]
""",
                """\
def extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1]
""",
            ),
            unchanged("src/sample/__init__.py", ""),
        ),
        visible_tests="""\
from sample.files import extension


def test_simple_extension() -> None:
    assert extension("report.txt") == "txt"
""",
        hidden_tests="""\
from sample.files import extension


def test_multiple_dots() -> None:
    assert extension("archive.tar.gz") == "gz"


def test_no_extension() -> None:
    assert extension("README") == ""
""",
    ),
)


PYPROJECT = """\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hewn-benchmark-fixture"
version = "0.0.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
pythonpath = ["src"]
"""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def build_fixture(
    spec: FixtureSpec,
    root: Path,
) -> None:
    fixture_root = root / spec.name

    if fixture_root.exists():
        shutil.rmtree(fixture_root)

    repository = fixture_root / "repository"
    evaluator = fixture_root / "evaluator"

    for file_spec in spec.files:
        write(
            repository / file_spec.path,
            file_spec.buggy,
        )

    write(repository / "pyproject.toml", PYPROJECT)
    write(
        repository / "tests/test_regression.py",
        spec.visible_tests,
    )
    write(
        evaluator / "test_task.py",
        spec.hidden_tests,
    )

    reference = fixture_root / "reference"

    shutil.copytree(repository, reference)

    for file_spec in spec.files:
        if file_spec.fixed is not None:
            write(
                reference / file_spec.path,
                file_spec.fixed,
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "research/016-building-hewn/fixtures"
        ),
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    expected_names = {spec.name for spec in FIXTURES}

    for child in args.out.iterdir():
        if (
            child.is_dir()
            and child.name not in expected_names
        ):
            shutil.rmtree(child)

    for spec in FIXTURES:
        build_fixture(spec, args.out)

    manifest = {
        "fixture_count": len(FIXTURES),
        "fixtures": [spec.name for spec in FIXTURES],
        "note": (
            "Repository contains only agent-visible files. "
            "Evaluator tests are stored outside the repository. "
            "Reference contains the deterministic known-good patch "
            "and is evaluator-only."
        ),
    }

    write(
        args.out / "manifest.json",
        json.dumps(manifest, indent=2) + "\n",
    )

    print(f"Built {len(FIXTURES)} fixtures in {args.out}")


if __name__ == "__main__":
    main()