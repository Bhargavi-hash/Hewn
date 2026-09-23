from sample.users import normalize_username


def test_lowercase() -> None:
    assert normalize_username("Alice") == "alice"
