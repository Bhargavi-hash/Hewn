def retry_delay(base: int, attempt: int) -> int:
    return base * attempt
