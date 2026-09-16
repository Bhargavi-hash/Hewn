# Module 2 — Conclusions

## Question

How much reasoning can we remove from a small model by giving it better
repository actions?

## Findings

The primitive benchmark exposed failures at several different layers rather
than one generic retrieval problem.

First, the model repeatedly attempted to call `search_text` with an explicit
path even though the original tool accepted only a query. Adding an authorized
workspace-relative search scope converted that previously invalid action into
a legitimate operation.

Second, raw text search returned both definitions and references. An AST-backed
`find_symbol` tool moved definition identification from probabilistic model
reasoning into deterministic program analysis.

Across one run of each configuration, deterministic task success changed from
0/9 with the primitive vocabulary, to 1/9 with scoped search, to 3/9 after
adding semantic symbol lookup.

These values are observations from a small controlled engineering experiment,
not general performance estimates.

## What Better Tools Solved

Better tools reduced reasoning required when the desired repository operation
was already clear.

For exact-symbol lookup, the model can request a definition directly rather
than interpret a collection of textual matches.

## What Better Tools Did Not Solve

Tools did not reliably make the model decide to inspect the repository.

Several tasks still ended without any tool call.

Conceptual questions were particularly difficult because they require mapping
behavioral intent to unknown repository concepts before exact symbol lookup is
possible.

Protocol encoding failures also remained independent of repository retrieval.

## Design Decision

Hewn will retain:

- workspace-scoped `search_text`
- AST-backed Python `find_symbol`

The project will not continue adding specialized tools merely to improve this
small benchmark.

The next architectural problem is repository understanding: representing
symbols, files, relationships, and structure so that conceptual questions can
be grounded before exact lookup.

## Module 2 Takeaway

Tool design is part of agent intelligence.

A useful tool does not make the model intrinsically smarter. It changes the
problem the model must solve by moving operations that software can perform
reliably out of probabilistic reasoning.

The benefit has a boundary: semantic actions help only when the agent can
select them. Repository understanding and action selection remain separate
problems.