from __future__ import annotations

from normalize_pytest import normalize_pytest_output


def test_normalizes_assertion_failure() -> None:
    raw = """
============================= FAILURES =============================
________________________ test_multiply _________________________

    def test_multiply() -> None:
>       assert multiply(4, 3) == 12
E       assert 7 == 12

test_calculator.py:5: AssertionError
======================= short test summary info ===================
FAILED test_calculator.py::test_multiply - assert 7 == 12
1 failed, 2 passed in 0.03s
"""

    result = normalize_pytest_output(raw)

    assert result == {
        "verification": "failed",
        "tool": "pytest",
        "failed_checks": [
            {
                "test": "test_calculator.py::test_multiply",
                "exception": "AssertionError",
                "assertion": "assert 7 == 12",
                "location": "test_calculator.py:5",
            }
        ],
        "summary": {
            "failed": 1,
            "passed": 2,
            "errors": 0,
        },
    }


def test_normalizes_runtime_exception() -> None:
    raw = """
============================= FAILURES =============================
______________________ test_fallback ______________________

    def test_fallback() -> None:
>       display_name({"name": "Ada"})

profile = {'name': 'Ada'}

    def display_name(profile: dict[str, str]) -> str:
>       return profile["nickname"]
E       KeyError: 'nickname'

profile.py:2: KeyError
======================= short test summary info ===================
FAILED test_profile.py::test_fallback - KeyError: 'nickname'
1 failed, 1 passed in 0.04s
"""

    result = normalize_pytest_output(raw)

    assert result == {
        "verification": "failed",
        "tool": "pytest",
        "failed_checks": [
            {
                "test": "test_profile.py::test_fallback",
                "exception": "KeyError",
                "message": "'nickname'",
                "location": "profile.py:2",
            }
        ],
        "summary": {
            "failed": 1,
            "passed": 1,
            "errors": 0,
        },
    }


def test_does_not_infer_a_repair() -> None:
    raw = """
============================= FAILURES =============================
______________________ test_timeout ______________________

    def request_timeout() -> int:
>       return DEFAULT_TIMEOUT
E       NameError: name 'DEFAULT_TIMEOUT' is not defined

client.py:5: NameError
======================= short test summary info ===================
FAILED test_client.py::test_timeout - NameError: name 'DEFAULT_TIMEOUT' is not defined
1 failed, 1 passed in 0.03s
"""

    result = normalize_pytest_output(raw)

    serialized = repr(result)

    assert "REQUEST_TIMEOUT" not in serialized
    assert "suggested_fix" not in serialized
    assert "diagnosis" not in serialized