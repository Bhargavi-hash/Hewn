from __future__ import annotations

import pytest

from hewn.context.policy import ContextPolicy


def test_default_policy_matches_module_5_decisions() -> None:
    policy = ContextPolicy()

    assert policy.semantic_evidence_limit == 3
    assert policy.bounded_source_limit == 800


def test_semantic_evidence_limit_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="Semantic evidence limit must be at least 1",
    ):
        ContextPolicy(
            semantic_evidence_limit=0,
        )


def test_bounded_source_limit_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="Bounded source limit must be at least 1",
    ):
        ContextPolicy(
            bounded_source_limit=0,
        )