from status import job_status, user_status


def test_user_status() -> None:
    assert user_status(True) == "active"
    assert user_status(False) == "pending"


def test_job_status_is_preserved() -> None:
    assert job_status(True) == "done"
    assert job_status(False) == "pending"
