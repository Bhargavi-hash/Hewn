from sample.slug import make_slug


def test_slug_words() -> None:
    assert make_slug("Hello World") == "hello-world"
