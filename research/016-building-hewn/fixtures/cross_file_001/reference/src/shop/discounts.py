def apply_percentage_discount(
    subtotal: float,
    percent: float,
) -> float:
    return subtotal * (1 - percent / 100)
