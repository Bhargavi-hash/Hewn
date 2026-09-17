# Conclusions - Module 5: Context Engineering

## Experiment 004 decision

Do not adopt unconditional whole-symbol source or mixed context.

The model-level ablation showed that representation affects more than context
size. In this nine-task run, mixed structural-plus-source evidence improved
performance on the conceptual subset and eliminated observed protocol errors,
but it required substantially more context and did not improve the
exact-symbol subset.

The next question is therefore not whether Hewn should always expose source.
It is whether Hewn can preserve the observed benefit of source-aware context
while exposing substantially less source code.

### Decision

Proceed to a source-granularity ablation.

Keep fixed:

- retrieval ranking,
- hybrid routing,
- top-3 unique-file evidence selection,
- task set,
- coding model,
- embedding model,
- temperature,
- prompt,
- tool availability,
- scoring.

Vary only how much source is represented.

Do not yet optimize evidence ordering or introduce benchmark-specific
retrieval rules.

## After Experiment 005

Source-aware context remains useful enough to retain, but whole-symbol
source should not become Hewn's unconditional context representation.

On the four conceptual tasks examined in Experiment 005, an
800-character bounded-source representation matched whole-symbol
source's aggregate 2/4 success count while using approximately 53.7%
fewer context characters on average.

This is not evidence that bounded source is universally equivalent to
whole source. The two representations succeeded on different tasks.

The result instead strengthens a more general design direction:
repository context should be query-dependent.

Exact-symbol questions may need only compact structural evidence.
Conceptual questions can benefit from implementation evidence, but the
usefulness of that evidence is not monotonic in source volume.

Do not tune additional source-length thresholds on the current four-task
subset. Doing so would risk benchmark-specific optimization.

The next experiments should investigate context composition and
organization while keeping retrieval and source-granularity mechanisms
fixed.

## After Experiment 006

Context organization is part of the effective reasoning system.

In the four-task evidence-position diagnostic, moving the
benchmark-relevant evidence to the final position reduced aggregate
success from 3/4 under retrieval order to 1/4 while context content and
size remained fixed.

This establishes evidence position as a variable worth studying in Hewn,
but it does not establish that relevant evidence should always appear
first. The label-aware position manipulations were diagnostic controls,
not deployable algorithms.

Hewn should therefore distinguish retrieval ranking from final context
ordering. Retrieval determines which evidence is selected; context
engineering determines how selected evidence is presented to the model.

The experiment also exposed run-to-run variation between nominally
equivalent bounded-source conditions in Experiments 005 and 006.
Repeated-trial evaluation should be introduced in the later evaluation
module before making broad quantitative claims.

Next, test a label-free context ordering policy rather than tuning
position against benchmark answers.

## After Experiment 007

Evidence ordering matters, but repository topology alone is not a
sufficient ordering policy.

Experiment 006 showed that changing evidence position can alter model
behavior while evidence content and size remain fixed.

Experiment 007 then tested whether Hewn's deterministic file dependency
graph could provide a deployable ordering rule. It did not outperform
semantic retrieval order in this four-task run.

Dependency-first changed all four contexts and produced protocol failures
on all four. Dependent-first changed three contexts and succeeded on one
of those changed cases.

The important distinction is:

- semantic retrieval rank is query-relative;
- dependency rank is repository-relative.

Reordering semantically retrieved evidence solely according to repository
topology can discard useful query-relative ordering information.

For now, preserve semantic retrieval order after evidence selection.
Retain repository dependencies as a separate structural signal rather
than using them as an unconditional context-ordering rule.

## After Experiment 008

File-level diversity is worth retaining as a conservative default, but
the current experiment provides limited causal evidence for its effect
on model success.

Raw Top-3 and unique-file Top-3 differed on only two of four conceptual
tasks. On those changed tasks, unique-file selection never hurt:
nav-006 succeeded under both policies and nav-009 succeeded only under
unique-file selection.

The aggregate success difference cannot be interpreted as a diversity
effect because nav-008 produced different outcomes despite identical
evidence selection and context size.

The primary engineering justification for unique-file selection is
therefore currently defensive: it prevents a small evidence budget from
being consumed by multiple symbols from one file while preserving
retrieval order.

Repeated-trial evaluation on a larger and less self-referential task set
is required before making stronger claims about diversity.