def normalize_name(value: str) -> str:
    return value.strip()


def stable_identifier(name: str) -> str:
    return f"user:{name}"
