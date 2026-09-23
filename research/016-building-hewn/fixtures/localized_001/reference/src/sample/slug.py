import re


def make_slug(value: str) -> str:
    value = value.lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")
