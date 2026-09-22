def active_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        record
        for record in records
        if record.get("enabled") is True
    ]
