# Module 10 — Persistent Repository Intelligence

## Central question

Can persistent repository-specific knowledge reduce repeated discovery work
and improve coding-agent decisions across related tasks without allowing
stale, incorrect, or irrelevant memory to override current repository
evidence?

## Motivation

Hewn can already inspect repository structure, retrieve relevant evidence,
construct bounded context, edit files, execute verification, and enforce
runtime authority.

Those mechanisms primarily reason from the repository as it exists during
the current run.

A coding agent working repeatedly in the same repository may rediscover the
same facts:

- architectural boundaries,
- important symbols,
- file relationships,
- verification commands,
- conventions,
- previous failures,
- decisions established during earlier tasks.

Repeated discovery consumes tool calls, model context, and latency.

Persistent knowledge could reduce that cost.

Persistence also introduces a new failure mode: remembered information can
become stale, incorrect, overgeneralized, or irrelevant.

The objective is therefore not to maximize remembered information.

The objective is to determine whether a small, evidence-grounded repository
memory improves later work while remaining subordinate to current repository
state.

## Primary hypothesis

For related sequential repository tasks, a small structured repository memory
can reduce repeated discovery operations while preserving or improving
behavioral task success relative to stateless execution.

## Secondary hypotheses

1. Repository memory should store structured claims rather than raw
   conversation history.

2. Every persisted claim should retain provenance sufficient to explain where
   it came from.

3. Current repository evidence should outrank remembered repository state when
   they conflict.

4. Memory usefulness depends on selective retrieval rather than injecting the
   entire memory store into every task.

5. Deterministic invalidation can eliminate some stale-memory failures before
   model reasoning is required.

6. Failed executions and corrections may provide useful operational memory,
   but should remain distinguishable from architectural facts.

## Research principle

Memory is evidence, not authority.

A persisted repository claim may help Hewn decide what to inspect or consider,
but it must not:

- grant tool authority,
- bypass workspace confinement,
- bypass verification,
- override current repository evidence.

## In scope

- repository-scoped persistent knowledge,
- structured memory records,
- provenance,
- confidence/status metadata,
- deterministic freshness checks,
- selective memory retrieval,
- architectural relationships,
- operational repository knowledge,
- historical failure/correction knowledge,
- sequential-task evaluation,
- stale-memory evaluation,
- memory utility and cost.

## Out of scope

- user-profile memory,
- cross-user memory,
- semantic memory learned across unrelated repositories,
- model-weight training,
- autonomous authority inference,
- long-term cloud synchronization,
- distributed memory services,
- vector-database infrastructure,
- general knowledge bases,
- Module 11 large-scale benchmarking.

## Success criteria

Module 10 should answer separately:

1. Does persistent repository knowledge reduce rediscovery?
2. Does it improve behavioral task success?
3. What additional context/storage cost does it introduce?
4. Can stale memory be detected or safely subordinated to current evidence?
5. Which classes of repository knowledge are worth persisting?

A successful module does not require memory to improve every metric.

Negative or neutral results should remain visible.