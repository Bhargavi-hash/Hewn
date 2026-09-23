from sample.boolean import parse_bool


def test_false() -> None:
    assert parse_bool("false") is False


def test_surrounding_whitespace() -> None:
    assert parse_bool(" YES ") is True
