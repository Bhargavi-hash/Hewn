# Module 6 Conclusions

No conclusions yet.

Production editing decisions will be based on measured failure modes rather than assumed advantages of a particular editing representation.

# Module 6 Conclusions — How Coding Agents Edit Code

## Research question

What editing abstraction lets a small coding model modify repository code
reliably while minimizing unintended changes and recovery work?

## Answer from the current experiments

The experiments do not justify replacing exact text replacement with a more
general patch primitive.

On the six frozen editing tasks, exact replacement was expressive enough to
represent localized modification, insertion through an existing anchor,
multiple changes within a file, and coordinated changes across files.

The more important distinction was between the mutation primitive and the
control structure around it.

A single exact replacement was too restrictive for some multi-location
tasks. A conversational sequence of replacements introduced repeated
rejections and edit oscillation. A one-shot structured batch could represent
multiple exact replacements without requiring the model to manage that
conversation.

The resulting candidate design is therefore:

1. The model proposes a complete structured batch.
2. Hewn deterministically validates every replacement.
3. The complete batch is simulated before mutation.
4. Any invalid edit rejects the complete batch.
5. A valid batch is committed atomically.
6. Execution-based correctness checking occurs after the edit layer.

## What deterministic validation contributes

Validation should not be delegated to the model when Hewn can determine the
answer mechanically.

The current evidence supports checking at least:

- workspace path safety,
- file existence,
- text encoding,
- non-empty anchors,
- rejection of no-op replacements,
- existence of the target text,
- uniqueness of the target text at the point of application.

This makes invalid transformations visible rather than silently guessing
where or how to apply them.

Experiment 005 did not show that a single precise validation-feedback turn
was sufficient for the tested 1.5B model to recover invalid batches.
Deterministic validation should therefore currently be treated primarily as
a safety and correctness boundary, not as evidence of reliable model
self-repair.

## Atomicity

Atomic batch application is preferable to partially committing a
multi-location proposal before discovering that a later edit is invalid.

The evaluator demonstrated that exact replacements can be simulated against
an evolving in-memory repository state before any files are written.

This permits later edits in the same batch to target text created by earlier
edits while preserving all-or-nothing repository mutation.

## What the experiments did not establish

These experiments used six small synthetic Python fixtures and one local
model configuration with one run per task.

They do not establish that exact replacement is sufficient for arbitrary
repositories or large refactors.

They do not establish that atomic batches outperform general patch formats.

They do not establish reliable recovery from validation feedback.

They do not establish that the observed behavior generalizes to other model
sizes, model families, languages, or repositories.

Temperature zero also does not guarantee deterministic model behavior.

Broader comparisons and repeated trials belong in the evaluation module.

## Deferred editing primitives

Do not add a general patch, AST rewrite, line-number editor, or dedicated
insertion primitive solely because other coding agents expose them.

Introduce another editing primitive only when a measured task distribution
shows a transformation that the current representation cannot express
reliably or economically.

## Boundary with Module 7

Module 6 evaluates how a proposed transformation is represented, validated,
and applied.

It does not attempt to determine whether an applicable transformation is
behaviorally correct through model-visible compiler, test, or linter
feedback.

Several Module 6 failures were successfully applied edits whose semantics
were wrong or incomplete. Those failures motivate the next question:

Can deterministic execution feedback help a small model diagnose and repair
a semantically incorrect but successfully applied change?

That is the subject of Module 7.