from sample.numbers import clamp


def test_inside_range() -> None:
    assert clamp(5, 0, 10) == 5


def test_upper_boundary() -> None:
    assert clamp(15, 0, 10) == 10
