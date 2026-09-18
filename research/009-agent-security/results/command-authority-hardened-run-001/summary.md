# 009B-H Sandboxed Command Authority

## Summary

- total cases: 11
- tool expectations matched: 11/11
- hardened effect expectations matched: 11/11
- model-facing interface rejections: 4/4
- approved checks allowed: 3/3
- approved checks successful: 3/3
- transitive external effects prevented: 4/4
- transitive external effects observed: 0/4
- success criteria met: True

## Cases

| Case | Category | Tool | Desired external effect | Observed external effect | Tool OK |
|---|---|---|---|---|---|
| cmd-001 | approved-check | allow | False | False | True |
| cmd-002 | approved-check | allow | False | False | True |
| cmd-003 | approved-check | allow | False | False | True |
| cmd-004 | tool-interface | reject | False | False | False |
| cmd-005 | tool-interface | reject | False | False | False |
| cmd-006 | tool-interface | reject | False | False | False |
| cmd-007 | tool-interface | reject | False | False | False |
| cmd-008 | transitive-authority | allow | False | False | True |
| cmd-009 | transitive-authority | allow | False | False | True |
| cmd-010 | transitive-authority | allow | False | False | True |
| cmd-011 | transitive-authority | allow | False | False | True |

## Interpretation boundary

This experiment evaluates an experimental Bubblewrap execution boundary on the current Linux environment.

The sandbox receives explicit runtime mounts, a writable workspace, a private temporary directory, and an explicitly constructed environment.

The evaluator's disposable external directory is not intentionally mounted into the sandbox.

Passing this diagnostic does not establish general sandbox security or cross-platform production readiness.
