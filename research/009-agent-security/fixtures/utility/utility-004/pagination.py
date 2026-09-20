from defaults import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


def page_size(requested: int | None) -> int:
    if requested is None:
        return DEFAULT_PAGE_SIZE

    return min(requested, MAX_PAGE_SIZE)