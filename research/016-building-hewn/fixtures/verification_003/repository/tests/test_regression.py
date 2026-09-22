from sample.files import extension


def test_simple_extension() -> None:
    assert extension("report.txt") == "txt"
