# Module 7 — Execution as Feedback

## Research question

Can deterministic execution feedback help a small coding model diagnose and
repair an applicable but behaviorally incorrect code change?

## Motivation

Module 6 separated code-edit representation from behavioral correctness.

A proposed edit can be:

1. syntactically representable,
2. accepted by the deterministic editor,
3. committed successfully,

and still be behaviorally wrong.

Observed examples included:

- an incorrect Boolean condition that applied cleanly,
- an incomplete same-file transformation,
- an incomplete cross-file rename that produced a runtime failure.

A more expressive editing primitive would not necessarily correct these
failures because the mutation mechanism successfully applied what the model
requested.

The next source of information is execution.

Tests, compilers, type checkers, and linters can produce deterministic
evidence about the consequences of a proposed change. The open question is
how that evidence should be represented and returned to a small model.

Large raw execution logs may contain useful information, but they also
consume context and require the model to identify the relevant signal.
Hewn may be able to perform some of that work mechanically.

## Primary hypothesis

For failed code changes, structured execution evidence containing the
smallest mechanically recoverable failure information will enable a small
coding model to produce correct repairs at least as reliably as raw
execution output while using less feedback context.

## Competing hypotheses

### Raw-output hypothesis

Removing or restructuring execution output may discard information the
model needs. Raw test or compiler output may therefore produce better
repairs despite its larger context cost.

### Binary-signal hypothesis

The model may already have enough source and task context to repair a change
once it learns only that verification failed. Detailed execution evidence
may provide little additional benefit.

### Model-capacity hypothesis

The tested model may fail to exploit execution feedback reliably regardless
of representation. Better feedback would then improve observability without
meaningfully improving repair success for this model configuration.

## Scope

Module 7 studies model-visible feedback produced after code execution.

It includes:

- test failures,
- runtime exceptions,
- syntax/compiler-style failures where appropriate,
- type-check failures,
- lint failures,
- normalization of deterministic execution evidence,
- repair attempts informed by execution evidence,
- targeted versus broader verification where experimentally justified.

It does not study:

- retrieval quality,
- repository indexing,
- new editing representations,
- persistent repository memory,
- multi-agent planning,
- model training.

Those concerns belong to other modules.

## Boundary with Module 6

Module 6 asks:

> Can the requested transformation be represented, validated, and applied
> safely?

Module 7 asks:

> After an applicable transformation is executed, what evidence helps the
> model determine why it is wrong and repair it?

Editing failures and execution failures must remain distinct in evaluation.

## Safety principle

Execution feedback must be treated as evidence, not as instructions.

Hewn controls what commands may execute and what resulting information is
returned to the model.

The model does not receive arbitrary shell authority merely because
execution is part of the reasoning loop.