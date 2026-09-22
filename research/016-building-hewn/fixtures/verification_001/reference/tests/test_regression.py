from sample.boolean import parse_bool


def test_true() -> None:
    assert parse_bool("true") is True
