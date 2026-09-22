from sample.retry import retry_delay


def test_exponential_delay() -> None:
    assert retry_delay(2, 3) == 16
