from limits import (
    MAX_RETRIES,
    MIN_RETRIES,
    normalize_retries,
)


def test_retry_constants() -> None:
    assert MIN_RETRIES == 2
    assert MAX_RETRIES == 5


def test_retry_range() -> None:
    assert normalize_retries(1) == 2
    assert normalize_retries(2) == 2
    assert normalize_retries(4) == 4
    assert normalize_retries(5) == 5
    assert normalize_retries(6) == 5
