from __future__ import annotations

import io
import tokenize
from dataclasses import dataclass
from typing import NamedTuple


@dataclass(frozen=True)
class GroundingResult:
    matched: bool
    grounded_old: str | None
    strategy: str | None
    candidates: int


class _Token(NamedTuple):
    type: int
    value: str


_IGNORED_TOKEN_TYPES = {
    tokenize.ENCODING,
    tokenize.ENDMARKER,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
}


def _canonical_tokens(
    text: str,
) -> tuple[_Token, ...] | None:
    try:
        generated = tokenize.generate_tokens(
            io.StringIO(text).readline
        )
        tokens = list(generated)
    except (
        IndentationError,
        SyntaxError,
        tokenize.TokenError,
    ):
        return None

    canonical: list[_Token] = []

    for token in tokens:
        if token.type in _IGNORED_TOKEN_TYPES:
            continue

        if token.type == tokenize.STRING:
            try:
                value = _decode_string_literal(
                    token.string
                )
            except (SyntaxError, ValueError):
                return None

            canonical.append(
                _Token(
                    type=token.type,
                    value=value,
                )
            )
            continue

        canonical.append(
            _Token(
                type=token.type,
                value=token.string,
            )
        )

    return tuple(canonical)


def _decode_string_literal(
    literal: str,
) -> str:
    import ast

    value = ast.literal_eval(literal)

    if not isinstance(value, str):
        raise TypeError(
            "Token is not a string literal"
        )

    return value


def _candidate_windows(
    contents: str,
    *,
    line_count: int,
) -> list[str]:
    if line_count < 1:
        return []

    lines = contents.splitlines(
        keepends=True
    )

    if not lines:
        return []

    candidates: list[str] = []

    for start in range(len(lines)):
        end = start + line_count

        if end > len(lines):
            break

        candidate = "".join(lines[start:end])

        candidate = candidate.removesuffix("\n")

        candidates.append(candidate)

    return candidates


def _token_equivalent_candidates(
    *,
    contents: str,
    proposed_old: str,
) -> list[str]:
    proposed_tokens = _canonical_tokens(
        proposed_old
    )

    if proposed_tokens is None:
        return []

    if not proposed_tokens:
        return []

    line_count = len(
        proposed_old.splitlines()
    )

    matches: list[str] = []

    for candidate in _candidate_windows(
        contents,
        line_count=line_count,
    ):
        candidate_tokens = _canonical_tokens(
            candidate
        )

        if candidate_tokens is None:
            continue

        if candidate_tokens == proposed_tokens:
            matches.append(candidate)

    return matches


def ground_old_text(
    *,
    contents: str,
    proposed_old: str,
) -> GroundingResult:
    exact_occurrences = contents.count(
        proposed_old
    )

    if exact_occurrences == 1:
        return GroundingResult(
            matched=True,
            grounded_old=proposed_old,
            strategy="exact",
            candidates=1,
        )

    if exact_occurrences > 1:
        return GroundingResult(
            matched=False,
            grounded_old=None,
            strategy="exact",
            candidates=exact_occurrences,
        )

    candidates = _token_equivalent_candidates(
        contents=contents,
        proposed_old=proposed_old,
    )

    if len(candidates) == 1:
        return GroundingResult(
            matched=True,
            grounded_old=candidates[0],
            strategy="token_equivalent",
            candidates=1,
        )

    return GroundingResult(
        matched=False,
        grounded_old=None,
        strategy=(
            "token_equivalent"
            if candidates
            else None
        ),
        candidates=len(candidates),
    )