from __future__ import annotations

from ground_edit import ground_old_text


def test_exact_unique_match() -> None:
    contents = (
        "def multiply(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )

    result = ground_old_text(
        contents=contents,
        proposed_old="return a + b",
    )

    assert result.matched
    assert result.grounded_old == "return a + b"
    assert result.strategy == "exact"
    assert result.candidates == 1


def test_quote_style_difference_is_grounded() -> None:
    contents = (
        "def display_name("
        "profile: dict[str, str]"
        ") -> str:\n"
        '    return profile["nickname"]\n'
    )

    result = ground_old_text(
        contents=contents,
        proposed_old=(
            "return profile['nickname']"
        ),
    )

    assert result.matched
    assert result.grounded_old == (
        '    return profile["nickname"]'
    )
    assert result.strategy == "token_equivalent"
    assert result.candidates == 1


def test_insignificant_horizontal_whitespace_is_grounded() -> None:
    contents = (
        "def add(a: int, b: int) -> int:\n"
        "    return a+b\n"
    )

    result = ground_old_text(
        contents=contents,
        proposed_old="return a + b",
    )

    assert result.matched
    assert result.grounded_old == (
        "    return a+b"
    )
    assert result.strategy == "token_equivalent"
    assert result.candidates == 1


def test_different_identifier_is_not_grounded() -> None:
    contents = (
        "from config import REQUEST_TIMEOUT\n\n"
        "def request_timeout() -> int:\n"
        "    return DEFAULT_TIMEOUT\n"
    )

    result = ground_old_text(
        contents=contents,
        proposed_old=(
            "from config import DEFAULT_TIMEOUT"
        ),
    )

    assert not result.matched
    assert result.grounded_old is None
    assert result.strategy is None
    assert result.candidates == 0


def test_nonexistent_assignment_is_not_grounded() -> None:
    contents = "REQUEST_TIMEOUT = 10\n"

    result = ground_old_text(
        contents=contents,
        proposed_old="DEFAULT_TIMEOUT = 10",
    )

    assert not result.matched
    assert result.grounded_old is None
    assert result.strategy is None
    assert result.candidates == 0


def test_ambiguous_exact_match_is_rejected() -> None:
    contents = (
        "def first() -> str:\n"
        '    return "active"\n\n'
        "def second() -> str:\n"
        '    return "active"\n'
    )

    result = ground_old_text(
        contents=contents,
        proposed_old='return "active"',
    )

    assert not result.matched
    assert result.grounded_old is None
    assert result.strategy == "exact"
    assert result.candidates == 2


def test_ambiguous_token_equivalent_match_is_rejected() -> None:
    contents = (
        "def first(profile: dict[str, str]) -> str:\n"
        '    return profile["nickname"]\n\n'
        "def second(profile: dict[str, str]) -> str:\n"
        '    return profile["nickname"]\n'
    )

    result = ground_old_text(
        contents=contents,
        proposed_old=(
            "return profile['nickname']"
        ),
    )

    assert not result.matched
    assert result.grounded_old is None
    assert result.strategy == "token_equivalent"
    assert result.candidates == 2


def test_semantically_different_expression_is_not_grounded() -> None:
    contents = (
        "def can_delete(\n"
        "    authenticated: bool,\n"
        "    owner: bool,\n"
        "    admin: bool,\n"
        ") -> bool:\n"
        "    return authenticated and owner or admin\n"
    )

    result = ground_old_text(
        contents=contents,
        proposed_old=(
            "return authenticated and "
            "(owner or admin)"
        ),
    )

    assert not result.matched
    assert result.grounded_old is None
    assert result.strategy is None
    assert result.candidates == 0


def test_multiline_quote_difference_is_grounded() -> None:
    contents = (
        "def value(profile: dict[str, str]) -> str:\n"
        '    if "nickname" in profile:\n'
        '        return profile["nickname"]\n'
        '    return profile["name"]\n'
    )

    proposed = (
        "if 'nickname' in profile:\n"
        "    return profile['nickname']"
    )

    result = ground_old_text(
        contents=contents,
        proposed_old=proposed,
    )

    assert result.matched
    assert result.grounded_old == (
        '    if "nickname" in profile:\n'
        '        return profile["nickname"]'
    )
    assert result.strategy == "token_equivalent"
    assert result.candidates == 1


def test_replacement_text_is_not_part_of_grounding() -> None:
    contents = (
        'return profile["nickname"]\n'
    )

    proposed_new = (
        "return profile.get("
        "'nickname', profile['name'])"
    )

    result = ground_old_text(
        contents=contents,
        proposed_old=(
            "return profile['nickname']"
        ),
    )

    assert result.matched
    assert result.grounded_old == (
        'return profile["nickname"]'
    )

    assert proposed_new == (
        "return profile.get("
        "'nickname', profile['name'])"
    )