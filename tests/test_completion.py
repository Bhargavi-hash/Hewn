import pytest

from hewn.completion import CompletionPolicy, CompletionRequirement, VerificationState


def test_unknown_allows_completion() -> None:
    policy = CompletionPolicy()

    assert policy.verification_state is VerificationState.UNKNOWN
    assert policy.can_finish()


def test_failed_check_blocks_completion() -> None:
    policy = CompletionPolicy()

    policy.record_check(passed=False)

    assert policy.verification_state is VerificationState.FAILED
    assert not policy.can_finish()
    assert "latest verification check failed" in policy.rejection_reason()


def test_passed_check_allows_completion() -> None:
    policy = CompletionPolicy()

    policy.record_check(passed=True)

    assert policy.verification_state is VerificationState.PASSED
    assert policy.can_finish()


def test_repository_change_makes_unknown_verification_stale() -> None:
    policy = CompletionPolicy()

    policy.record_repository_change()

    assert policy.verification_state is VerificationState.STALE
    assert not policy.can_finish()


def test_repository_change_invalidates_passed_verification() -> None:
    policy = CompletionPolicy()
    policy.record_check(passed=True)

    policy.record_repository_change()

    assert policy.verification_state is VerificationState.STALE
    assert not policy.can_finish()


def test_repository_change_after_failure_becomes_stale() -> None:
    policy = CompletionPolicy()
    policy.record_check(passed=False)

    policy.record_repository_change()

    assert policy.verification_state is VerificationState.STALE
    assert not policy.can_finish()


def test_successful_check_after_stale_state_allows_completion() -> None:
    policy = CompletionPolicy()
    policy.record_repository_change()

    policy.record_check(passed=True)

    assert policy.verification_state is VerificationState.PASSED
    assert policy.can_finish()


def test_failed_check_after_stale_state_blocks_completion() -> None:
    policy = CompletionPolicy()
    policy.record_repository_change()

    policy.record_check(passed=False)

    assert policy.verification_state is VerificationState.FAILED
    assert not policy.can_finish()


def test_rejection_reason_is_invalid_when_completion_is_allowed() -> None:
    policy = CompletionPolicy()

    with pytest.raises(ValueError, match="Completion is not currently blocked"):
        policy.rejection_reason()

def test_verified_requirement_blocks_unknown() -> None:
    policy = CompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
    )

    assert not policy.can_finish()


def test_verified_requirement_allows_passed() -> None:
    policy = CompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
    )

    policy.record_check(passed=True)

    assert policy.can_finish()


def test_none_requirement_allows_unknown() -> None:
    policy = CompletionPolicy(
        requirement=CompletionRequirement.NONE,
    )

    assert policy.can_finish()