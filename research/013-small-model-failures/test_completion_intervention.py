from __future__ import annotations

from evaluate_completion_intervention import (
    EDIT_TOOL,
    MUTATION_FEEDBACK,
    MutationAwareCompletionPolicy,
)

from hewn.completion import (
    CompletionRequirement,
    VerificationState,
)
from hewn.tools import ToolCall, ToolResult


def make_edit_call() -> ToolCall:
    return ToolCall(
        name=EDIT_TOOL,
        arguments={
            "path": "src/sample/example.py",
            "old": "before",
            "new": "after",
        },
    )


def test_mutation_task_rejects_first_completion_with_targeted_feedback() -> None:
    policy = MutationAwareCompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
        mutation_required=True,
    )

    assert not policy.can_finish()
    assert policy.rejection_reason() == MUTATION_FEEDBACK

    assert policy.intervention_delivered
    assert not policy.edit_attempted


def test_mutation_feedback_is_delivered_only_once() -> None:
    policy = MutationAwareCompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
        mutation_required=True,
    )

    assert policy.rejection_reason() == MUTATION_FEEDBACK

    second_reason = policy.rejection_reason()

    assert second_reason != MUTATION_FEEDBACK
    assert "verification" in second_reason.lower()


def test_failed_replace_text_counts_as_edit_attempt() -> None:
    policy = MutationAwareCompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
        mutation_required=True,
    )

    policy.record_tool_attempt(
        call=make_edit_call(),
        result=ToolResult(
            ok=False,
            error="replacement failed",
        ),
    )

    assert policy.edit_attempted
    assert not policy.intervention_delivered

    assert not policy.can_finish()

    reason = policy.rejection_reason()

    assert reason != MUTATION_FEEDBACK
    assert "verification" in reason.lower()


def test_successful_replace_text_counts_as_edit_attempt() -> None:
    policy = MutationAwareCompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
        mutation_required=True,
    )

    policy.record_tool_attempt(
        call=make_edit_call(),
        result=ToolResult(
            ok=True,
            output="replacement applied",
        ),
    )

    assert policy.edit_attempted
    assert not policy.intervention_delivered

    assert not policy.can_finish()

    reason = policy.rejection_reason()

    assert reason != MUTATION_FEEDBACK
    assert "verification" in reason.lower()


def test_non_edit_tool_does_not_satisfy_mutation_gate() -> None:
    policy = MutationAwareCompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
        mutation_required=True,
    )

    policy.record_tool_attempt(
        call=ToolCall(
            name="find_symbol",
            arguments={"symbol": "example"},
        ),
        result=ToolResult(
            ok=True,
            output="example.py",
        ),
    )

    assert not policy.edit_attempted
    assert not policy.can_finish()
    assert policy.rejection_reason() == MUTATION_FEEDBACK


def test_non_mutation_task_preserves_verified_policy() -> None:
    policy = MutationAwareCompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
        mutation_required=False,
    )

    assert not policy.can_finish()

    reason = policy.rejection_reason()

    assert reason != MUTATION_FEEDBACK
    assert "verification" in reason.lower()
    assert not policy.intervention_delivered


def test_verified_completion_allowed_after_edit_attempt() -> None:
    policy = MutationAwareCompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
        mutation_required=True,
    )

    policy.record_tool_attempt(
        call=make_edit_call(),
        result=ToolResult(
            ok=True,
            output="replacement applied",
        ),
    )

    policy.record_check(
        passed=True,
    )

    assert (
        policy.verification_state
        is VerificationState.PASSED
    )
    assert policy.can_finish()
    assert not policy.intervention_delivered


def test_repository_change_after_verification_still_makes_state_stale() -> None:
    policy = MutationAwareCompletionPolicy(
        requirement=CompletionRequirement.VERIFIED,
        mutation_required=True,
    )

    policy.record_check(
        passed=True,
    )

    policy.record_tool_attempt(
        call=make_edit_call(),
        result=ToolResult(
            ok=True,
            output="replacement applied",
        ),
    )

    policy.record_repository_change()

    assert policy.edit_attempted
    assert (
        policy.verification_state
        is VerificationState.STALE
    )
    assert not policy.can_finish()

    reason = policy.rejection_reason()

    assert reason != MUTATION_FEEDBACK
    assert "repository changed" in reason.lower()
    assert "verification" in reason.lower()