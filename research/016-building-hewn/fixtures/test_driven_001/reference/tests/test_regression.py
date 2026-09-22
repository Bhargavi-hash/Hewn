from sample.paths import join_path


def test_join_avoids_duplicate_separator() -> None:
    assert join_path("/tmp/", "/report.txt") == "/tmp/report.txt"
