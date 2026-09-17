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

## Final Module 5 conclusion

Module 5 began with the question:

> How should Hewn select, budget, order, and represent retrieved repository evidence so that a small coding model can reason effectively without wasting context?

The experiments did not identify a single universally optimal context size or representation. Instead, they established several narrower design decisions.

### Decisions retained

For exact-symbol retrieval:

- use the deterministic exact-symbol result;
- keep the representation compact and structural;
- do not expand source automatically;
- do not add filler evidence.

For semantic retrieval:

- preserve semantic retrieval order;
- select up to 3 unique files;
- use bounded source with an 800-character per-symbol limit;
- retrieve a larger candidate pool before file-level deduplication.

Hewn does not currently use:

- dependency-aware evidence reordering;
- skip-to-fit character-budget packing;
- whole-source expansion by default.

### Evidence supporting those decisions

Fixed-count experiments showed that additional evidence can recover relevant files, but adding context beyond that point can increase text substantially without increasing mechanical retrieval coverage.

Character-budget experiments showed that a byte or character budget is not equivalent to a relevance policy: skip-to-fit packing can discard higher-ranked evidence while admitting smaller lower-ranked evidence.

Representation experiments showed that source-aware evidence is substantially more expensive than structural evidence, but the local coding-model experiment also showed that richer source-aware context can change model behavior and was associated with better conceptual-task performance in that run.

Bounded source matched whole-source aggregate success on the four-task source-granularity experiment while using substantially fewer characters, although the two representations succeeded on different tasks.

Evidence-position experiments showed that ordering can affect model behavior even when evidence content and total size are held fixed.

Dependency-aware ordering did not improve the four conceptual tasks and frequently produced protocol failures. Structural topology was therefore not adopted as a replacement for query-conditioned semantic ranking.

The diversity experiment provided limited causal evidence but supported file-level deduplication as a conservative policy that prevents a small evidence budget from being dominated by multiple symbols from one file.

### Production integration

The final production policy was implemented through a separation of responsibilities:

`retrieve_routed()` determines which repository evidence is relevant.

`ContextBuilder` determines what representation of that evidence enters model context.

`HewnSession` orchestrates retrieval, context construction, and the core `Agent`.

The core `Agent` remains independent of semantic retrieval infrastructure and accepts an optional prepared `ContextBundle`.

In the final nine-task integration run, production retrieval covered the expected file for all 9 tasks. End-to-end agent success was 1/9 without prepared context and 3/9 with production context.

The difference occurred entirely on exact-symbol tasks:

- no context: 1/5 exact, 0/4 conceptual;
- production context: 3/5 exact, 0/4 conceptual.

All four conceptual tasks had expected-file retrieval coverage under the production policy, but none produced a correct final answer.

### What Module 5 established

For this Hewn self-navigation benchmark, the repository-understanding, retrieval, and context pipeline can reliably place the mechanically expected file into the model's evidence set.

That does not imply that the model can reliably reason over the evidence.

The remaining conceptual failures demonstrate a boundary between evidence acquisition and downstream model behavior:

repository understanding
→ retrieval
→ context construction
→ model interpretation
→ tool/action selection
→ final response

Modules 3–5 primarily improve the first three stages. The final integration run shows that failures can remain after those stages succeed.

No broad accuracy, latency, or compute-efficiency claim is made from the single-run nine-task integration experiment. Repeated trials, unseen repositories, stronger statistical evaluation, and broader task distributions are deferred to Module 11.