from reporting.records import active_records


def active_count(records: list[dict[str, object]]) -> int:
    return len(active_records(records))
