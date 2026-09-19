from parser import normalize_format


def test_normalize_format_is_case_insensitive() -> None:
    assert normalize_format("  JSON  ") == "json"


def test_normalize_format_strips_whitespace() -> None:
    assert normalize_format(" yaml ") == "yaml"