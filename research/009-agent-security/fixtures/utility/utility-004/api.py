from pagination import page_size


def response_limit(requested: int | None) -> int:
    return page_size(requested)