from sample.slug import make_slug


def test_surrounding_punctuation() -> None:
    assert make_slug("  Hello World!!  ") == "hello-world"


def test_only_punctuation() -> None:
    assert make_slug("!!!") == ""
