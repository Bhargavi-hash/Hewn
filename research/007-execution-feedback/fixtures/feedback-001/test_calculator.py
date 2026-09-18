from calculator import multiply


def test_multiply_positive_values() -> None:
    assert multiply(4, 3) == 12


def test_multiply_negative_value() -> None:
    assert multiply(-2, 5) == -10