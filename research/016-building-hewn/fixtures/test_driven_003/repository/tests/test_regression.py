from sample.titles import format_title


def test_empty_title() -> None:
    assert format_title("   ") == "Hewn"
