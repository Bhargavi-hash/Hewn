import pytest

from pricing import discounted_price


def test_valid_discount() -> None:
    assert discounted_price(100.0, 0.25) == 75.0


@pytest.mark.parametrize("discount", [-0.1, 1.1])
def test_invalid_discount(discount: float) -> None:
    with pytest.raises(ValueError):
        discounted_price(100.0, discount)
