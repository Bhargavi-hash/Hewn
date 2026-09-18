from client import request_timeout
from config import REQUEST_TIMEOUT


def test_timeout_constant() -> None:
    assert REQUEST_TIMEOUT == 10


def test_timeout_behavior() -> None:
    assert request_timeout() == 10