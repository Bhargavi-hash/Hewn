from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class VerificationState(Enum):
    UNKNOWN = auto()
    FAILED = auto()
    STALE = auto()
    PASSED = auto()

class CompletionRequirement(Enum):
    NONE = auto()
    VERIFIED = auto()


@dataclass
class CompletionPolicy:
    requirement: CompletionRequirement = CompletionRequirement.NONE
    verification_state: VerificationState = VerificationState.UNKNOWN

    def record_check(self, *, passed: bool) -> None:
        self.verification_state = (
            VerificationState.PASSED
            if passed
            else VerificationState.FAILED
        )

    def record_repository_change(self) -> None:
        self.verification_state = VerificationState.STALE

    def can_finish(self) -> bool:
        if self.requirement is CompletionRequirement.VERIFIED:
            return self.verification_state is VerificationState.PASSED

        return self.verification_state in {
            VerificationState.UNKNOWN,
            VerificationState.PASSED,
        }

    def rejection_reason(self) -> str:
        if (
            self.requirement is CompletionRequirement.VERIFIED
            and self.verification_state is VerificationState.UNKNOWN
        ):
            return (
                "Cannot finish because this task requires verification "
                "and no successful verification has been observed."
            )

        if self.verification_state is VerificationState.FAILED:
            return (
                "Cannot finish because the latest verification check failed. "
                "Continue working and verify the repository again before finishing."
            )

        if self.verification_state is VerificationState.STALE:
            return (
                "Cannot finish because the repository changed after the latest "
                "verification. Run a verification check before finishing."
            )

        raise ValueError("Completion is not currently blocked")