# ADR 0001 — Tool Calls Are Untrusted Requests

## Status

Accepted

## Context

Language models used by Hewn can request actions that interact with the
developer's repository and execution environment.

Model output may be incorrect, malformed, influenced by repository content,
or intentionally manipulated through prompt injection.

Therefore, model-generated tool calls cannot be treated as trusted commands.

## Decision

Hewn treats every model-generated tool call as an untrusted request.

A tool request must pass through the harness before execution.

The intended lifecycle is:

1. Propose
2. Validate
3. Authorize
4. Execute
5. Normalize

The model proposes actions. The Hewn harness decides whether and how those
actions are executed.

## Consequences

Tool definitions require explicit schemas.

Unknown tools are rejected.

Arguments will be validated before execution.

Filesystem and command access will be constrained by policy.

Tool results will be normalized before being returned to the model.

This architecture creates an explicit trust boundary between model output
and the developer's machine.