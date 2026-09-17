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