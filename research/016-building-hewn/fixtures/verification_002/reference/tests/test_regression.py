from sample.retry import retry_delay


def test_zero_base_stays_zero() -> None:
    assert retry_delay(0, 3) == 0
