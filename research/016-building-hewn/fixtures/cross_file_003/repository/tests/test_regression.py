from reporting.summary import active_count


def test_all_active() -> None:
    records = [
        {"id": 1, "enabled": True},
        {"id": 2, "enabled": True},
    ]
    assert active_count(records) == 2
