from reporting.summary import active_count


def test_disabled_records_are_excluded() -> None:
    records = [
        {"id": 1, "enabled": True},
        {"id": 2, "enabled": False},
        {"id": 3, "enabled": True},
    ]
    assert active_count(records) == 2
