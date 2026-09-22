from sample.numbers import clamp


def test_below_range() -> None:
    assert clamp(-4, 0, 10) == 0
