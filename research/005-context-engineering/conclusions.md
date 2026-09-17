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