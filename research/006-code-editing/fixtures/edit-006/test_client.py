import config

from client import request_timeout


def test_timeout_behavior() -> None:
    assert request_timeout() == 10


def test_constant_was_renamed() -> None:
    assert hasattr(config, "REQUEST_TIMEOUT")
    assert config.REQUEST_TIMEOUT == 10
    assert not hasattr(config, "DEFAULT_TIMEOUT")
