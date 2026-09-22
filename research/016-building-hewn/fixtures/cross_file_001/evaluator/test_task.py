from shop.checkout import checkout_total


def test_percentage_discount() -> None:
    assert checkout_total(200.0, 25.0) == 150.0
