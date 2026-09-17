MIN_RETRIES = 1
MAX_RETRIES = 3


def normalize_retries(value: int) -> int:
    if value < MIN_RETRIES:
        return 0

    if value > MAX_RETRIES:
        return 3

    return value
