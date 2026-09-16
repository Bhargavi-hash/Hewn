## Experiment 002 — Search Interface Compatibility

### Observation

In Experiment 001, three exact-symbol tasks independently produced
`search_text` calls containing both `query` and `path`.

The Module 1 search tool accepts only `query`, so these calls were rejected
before search execution.

### Hypothesis

A search interface with an explicit optional path may better match the action
representation expected by the small model and therefore reduce tool-schema
failures.

### Treatment

Introduce a treatment search tool interface supporting:

- `query`: required search string
- `path`: optional workspace-relative search scope

The control remains the original Module 1 `search_text` interface.

### Controlled Variables

Keep fixed:

- model,
- quantization,
- inference settings,
- system prompt,
- task wording,
- completion policy,
- repository,
- evaluator.

Change only the search tool interface and its corresponding implementation.

### Primary Measurement

Compare exact-symbol tasks on:

- valid tool execution rate,
- task success,
- model calls,
- tool calls,
- protocol failures.

### Interpretation Boundary

Improvement would support the claim that tool-interface design can affect
small-model agent performance.

It would not establish that scoped search is universally superior or that
repository retrieval as a whole has been solved.