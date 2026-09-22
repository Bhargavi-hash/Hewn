from sample.tags import unique_tags


def test_duplicate_tags_are_removed() -> None:
    assert unique_tags(["python", "agent", "python"]) == [
        "python",
        "agent",
    ]
