from sample.files import extension


def test_multiple_dots() -> None:
    assert extension("archive.tar.gz") == "gz"


def test_no_extension() -> None:
    assert extension("README") == ""
