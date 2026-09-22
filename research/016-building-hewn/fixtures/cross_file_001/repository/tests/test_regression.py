from shop.checkout import checkout_total


def test_no_discount() -> None:
    assert checkout_total(100.0, 0.0) == 100.0
