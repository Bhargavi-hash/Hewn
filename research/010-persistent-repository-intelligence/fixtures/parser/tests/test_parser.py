from sample.parser import normalize_value


def test_normalize_value_trims_whitespace() -> None:
    assert normalize_value("  Alpha  ") == "Alpha"
