# Module 17: Hewn vs Frontier Coding Agents

## Goal

Compare the frozen Hewn v0.1 system against frontier coding agents on the
same repository-level task distribution.

The purpose is not to prove that Hewn is universally better or worse.

The experiment asks:

1. Which tasks can each system solve?
2. Where does each system fail?
3. How much repository modification is required?
4. How many regressions or unnecessary changes are introduced?
5. How much interaction, context, time, compute, and cost are required?
6. Which capabilities appear to come from the model, and which come from
   deterministic agent infrastructure?

## Frozen Hewn System

Hewn is evaluated from the tag:

    hewn-v0.1-eval-freeze

No Hewn architectural changes may be made after frontier-agent results are
observed and then attributed to the frozen comparison.

The historical Module 16C Hewn result remains part of the record.

## Comparison Principle

Frontier coding agents receive the same task description and initial
repository state as Hewn.

They may use their normal native coding-agent mechanisms.

They are not artificially constrained to reproduce Hewn's internal tool
protocol.

Correctness is determined externally using the same hidden behavioral and
regression evaluators wherever possible.

## Primary Metrics

- behavioral success
- hidden task-oracle success
- regression success

## Secondary Metrics

- changed files
- unnecessary changed files
- size of patch
- task-relevant edits
- model/agent turns where observable
- tool calls where observable
- verification attempts where observable
- wall time
- human intervention
- input/output tokens where observable
- monetary cost where observable
- local compute/resource use where observable

Unavailable metrics must be reported as unavailable rather than estimated
without evidence.

## Experimental Rules

1. The task set is frozen before frontier evaluation.
2. Initial repository state must be identical for every system.
3. Hidden evaluators are not shown to the evaluated agent.
4. Failed attempts remain in the result set.
5. No task-specific prompt repair is allowed after observing a failure.
6. No manual code edits are allowed during an evaluated run.
7. Human intervention must be recorded.
8. Hewn v0.1 remains frozen throughout the comparison.
9. Frontier systems may use their native agent mechanisms.
10. Claims must distinguish measured results from interpretation.
