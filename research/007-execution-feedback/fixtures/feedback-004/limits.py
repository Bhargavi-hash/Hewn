MIN_RETRIES = 2
MAX_RETRIES = 5


def normalize_retries(value: int) -> int:
    if value < MIN_RETRIES:
        return 0

    if value > MAX_RETRIES:
        return 3

    return value