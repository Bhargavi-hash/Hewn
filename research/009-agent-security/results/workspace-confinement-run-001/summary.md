# 009A Workspace Confinement Baseline

## Summary

- total cases: 11
- matched expectation: 11/11
- authorized allowed: 4/4
- unauthorized blocked: 7/7
- false accepts: []
- false rejects: []
- unexpected errors: []
- escaped paths: []
- external side effects: []

## Cases

| Case | Category | Expected | Observed | Match |
|---|---|---|---|---|
| path-001 | authorized | allow | allow | yes |
| path-002 | authorized | allow | allow | yes |
| path-003 | traversal | reject | reject | yes |
| path-004 | traversal | reject | reject | yes |
| path-005 | traversal | reject | reject | yes |
| path-006 | absolute | reject | reject | yes |
| path-007 | normalization | allow | allow | yes |
| path-008 | sibling-prefix | reject | reject | yes |
| path-009 | internal-symlink | allow | allow | yes |
| path-010 | external-symlink | reject | reject | yes |
| path-011 | external-symlink-descendant | reject | reject | yes |

## Interpretation boundary

This experiment measures path resolution through the current
`Workspace.resolve` implementation only. It does not establish
shell-command confinement, process isolation, or general agent
security.
