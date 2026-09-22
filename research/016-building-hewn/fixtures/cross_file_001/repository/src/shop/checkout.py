from shop.discounts import apply_percentage_discount


def checkout_total(subtotal: float, percent: float) -> float:
    return apply_percentage_discount(subtotal, percent)
