from sample.settings import DEFAULT_RETRIES


def request_policy() -> int:
    return DEFAULT_RETRIES


def stable_identifier(name: str) -> str:
    return f"user:{name}"
