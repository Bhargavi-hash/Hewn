from sample.client import request_policy


def test_request_policy_defaults() -> None:
    assert request_policy() == (2, 5)
