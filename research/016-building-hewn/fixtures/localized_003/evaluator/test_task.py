from sample.users import normalize_username


def test_surrounding_whitespace() -> None:
    assert normalize_username("  Alice  ") == "alice"
