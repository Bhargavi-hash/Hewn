from sample.settings import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_RETRY_COUNT,
)


def request_policy() -> tuple[int, int]:
    return (
        DEFAULT_RETRY_COUNT,
        DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )
