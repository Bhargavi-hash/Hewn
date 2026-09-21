# Module 13 — Why Small Models Fail

## Central research question

What failure modes prevent small coding models from completing repository-level
tasks, and which of those failures can be mitigated deterministically through
tools, context, decomposition, verification, or control-loop design?

## Primary hypothesis

Small coding models do not fail for a single reason. Repository-level task
failure is the observable result of distinct failure modes occurring at
different boundaries of the coding-agent system.

Some failures require greater model capability. Others can be reduced by
changing the surrounding agent system without increasing model size.

## Research principle

> A model failure is not automatically an agent failure.

Hewn should identify where a failure occurs before deciding how to compensate
for it.

## Questions

1. Which failure modes recur across small-model coding tasks?
2. Can those failures be localized to specific model/agent boundaries?
3. Which failures are reduced by better retrieval or context?
4. Which failures are reduced by deterministic tools or validation?
5. Which failures are reduced by decomposition or constrained output?
6. Which failures persist despite appropriate scaffolding?
7. When does additional scaffolding add cost without improving behavioral
   correctness?

## Non-goals

- Training or fine-tuning a model.
- Claiming that all small-model failures can be repaired by agent design.
- Comparing Hewn against frontier coding agents.
- Selecting a larger model solely to improve benchmark results.
- Retrofitting explanations to individual failures after observing them.

## Experimental rule

Failure categories and intervention rules must be defined before evaluating
whether an intervention succeeds.

Behavioral correctness remains the primary outcome. Protocol compliance,
tool selection, retrieval quality, edit validity, execution results, and
resource usage are diagnostic measurements rather than substitutes for
behavioral success.

Negative results remain part of the experimental record.
