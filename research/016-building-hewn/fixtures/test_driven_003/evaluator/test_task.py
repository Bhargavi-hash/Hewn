from sample.titles import format_title


def test_empty_string() -> None:
    assert format_title("") == "Hewn"


def test_whitespace_only_title() -> None:
    assert format_title("	  ") == "Hewn"
