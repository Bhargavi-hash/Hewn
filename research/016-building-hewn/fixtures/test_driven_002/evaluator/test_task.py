from sample.tags import unique_tags


def test_original_order_is_preserved() -> None:
    assert unique_tags(["b", "a", "b", "c", "a"]) == [
        "b",
        "a",
        "c",
    ]
