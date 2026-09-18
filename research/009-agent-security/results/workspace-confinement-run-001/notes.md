# 009A Workspace Confinement — Run 001 Notes

## Result

The existing `Workspace.resolve()` implementation matched the frozen
expectation on all 11 path-confinement cases.

- expected outcomes matched: 11/11
- authorized operations allowed: 4/4
- unauthorized operations blocked: 7/7
- false accepts: 0
- false rejects: 0
- resolved paths escaping the workspace: 0
- external filesystem side effects: 0

No production hardening was applied before this run.

## Interpretation

The current workspace capability boundary was sufficient for the path
classes exercised by the frozen 009A corpus.

The implementation canonicalizes the requested path with `Path.resolve()`
and then checks the canonical result with `Path.is_relative_to()` against
the canonical workspace root.

In this diagnostic, that mechanism correctly handled:

- ordinary repository-relative paths
- nested repository-relative paths
- parent traversal
- repeated parent traversal
- absolute external paths
- internal normalization
- sibling-prefix paths
- symlinks resolving inside the workspace
- symlinks resolving outside the workspace
- nonexistent descendants beneath an external-directory symlink

The sibling-prefix case is important because lexical string-prefix checks
can incorrectly treat a sibling such as `repo-evil` as belonging to
`repo`.

The external-directory symlink descendant is also useful because the
requested leaf does not need to exist for the existing symlinked parent
to reveal that the canonical destination lies outside the workspace.

## path-007 note

`path-007` resolves:

`src/../tests/test_main.py`

to:

`tests/test_main.py`

The fixture does not require the final file to exist.

This case measures authorization of a normalized repository-internal path,
not file-existence validation. Its observed `allow` result is therefore
consistent with the scope of 009A.

Existence and operation-specific requirements belong to the filesystem
tool layer rather than the workspace containment predicate itself.

## Decision

Do not modify `src/hewn/workspace.py` based on 009A.

The proposed hardened-path condition is not warranted by this experiment:
the existing implementation already satisfied every frozen path
confinement case.

Proceed to 009B to test command authority independently.

Passing 009A does not establish that Hewn is generally secure. It only
provides evidence for the path-confinement classes represented in the
frozen 009A corpus.

In particular, 009A does not test:

- shell-command confinement
- command composition
- interpreter indirection
- environment-variable exposure
- repository prompt injection
- arbitrary subprocess behavior
- operating-system isolation