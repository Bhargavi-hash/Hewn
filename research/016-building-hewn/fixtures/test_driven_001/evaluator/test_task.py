from sample.paths import join_path


def test_parent_with_trailing_separator() -> None:
    assert join_path("/var/log/", "app.log") == "/var/log/app.log"


def test_child_with_leading_separator() -> None:
    assert join_path("/var/log", "/app.log") == "/var/log/app.log"
