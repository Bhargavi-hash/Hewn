# Module 10 Experiments

## Experimental rule

Fixtures and evaluation criteria must be frozen before observing model behavior.

Do not modify task fixtures to improve results after model execution begins.

Use deterministic measurements wherever possible.

Single temperature-zero runs remain diagnostic. Repeated-trial claims belong
primarily to Module 11.

---

## 010A — Repeated discovery baseline

### Question

How much repository discovery does Hewn repeat across related sequential tasks
when no persistent repository knowledge is available?

### Conditions

A. Independent stateless tasks.

B. Same tasks in sequence, but without persistent memory between runs.

### Measure

- behavioral task success,
- model calls,
- tool calls,
- repository-read calls,
- search calls,
- structural inspection calls,
- repeated evidence accesses,
- prompt/context size,
- wall time.

### Purpose

Establish whether a measurable rediscovery problem exists before building a
memory mechanism.

If repeated discovery is negligible, the motivation for persistent memory is
weaker.

---

## 010B — Structured repository memory

### Question

Does a small structured memory reduce rediscovery on later related tasks?

### Intervention

Persist a bounded set of repository claims learned during earlier tasks.

Memory must be:

- repository-scoped,
- structured,
- provenance-bearing,
- selectively retrieved.

Do not inject the entire memory store.

### Compare

A. Stateless execution.

B. Structured-memory execution.

### Measure

All 010A metrics plus:

- memory records stored,
- memory records retrieved,
- memory records used in context,
- relevant-memory precision,
- relevant-memory recall where oracle labels are available,
- memory context characters/tokens.

### Primary diagnostic

Does memory reduce repeated repository discovery?

Behavioral success is reported separately.

---

## 010C — Stale memory

### Question

What happens when a previously correct repository claim conflicts with current
repository state?

### Protocol

1. Establish a valid memory record from repository version V1.
2. Mutate the fixture deterministically to version V2.
3. Run a related task with the old record still present.

### Conditions

A. Memory accepted without freshness validation.

B. Deterministic freshness validation before memory use.

C. Current repository evidence explicitly available alongside stale memory.

### Measure

- stale records retrieved,
- stale records rejected,
- stale claims reaching model context,
- behavioral success,
- incorrect edits attributable to stale memory,
- additional discovery required after invalidation.

### Purpose

A memory system that improves repeated work but silently trusts stale state is
not sufficient.

---

## 010D — What is worth remembering?

### Question

Which repository knowledge classes provide measurable value?

### Candidate classes

- structural,
- architectural,
- operational,
- historical failure,
- decision.

### Method

Use ablations rather than adding all memory categories simultaneously.

Compare later-task behavior and rediscovery with selected classes removed.

### Decision rule

Do not promote a memory class merely because it sounds useful.

It should either:

- reduce rediscovery,
- improve task behavior,
- prevent a repeated failure,
- or materially improve evidence selection.

---

## 010E — Synthesis

Integrate the evidence from 010A–010D.

Decide:

- whether persistent repository intelligence is earned,
- which record classes should enter production,
- what provenance is required,
- what freshness mechanism is required,
- how memory retrieval interacts with Module 4 retrieval,
- how memory enters Module 5 context,
- what remains research-only.

Do not make Module 11 benchmark claims here.