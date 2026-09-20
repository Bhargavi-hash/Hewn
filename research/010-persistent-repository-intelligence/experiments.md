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

Can a small set of structured repository-specific claims established
during an earlier task improve a related later task or reduce repeated
discovery compared with stateless repository retrieval?

### Hypothesis

Bounded structured memory can provide reusable repository relationships
that current stateless retrieval would otherwise need to reconstruct.
Memory may reduce repeated discovery and may improve behavioral success,
but either outcome is measured independently.

### Conditions

Each frozen 010A task pair is executed twice from an independent copy of
the same V0 fixture:

1. `stateless`
   - current repository retrieval only
   - no persistent records

2. `structured_memory`
   - identical current repository retrieval
   - bounded structured records established after task 1
   - records supplied to task 2 as explicitly labeled historical evidence

Task 2 begins from the actual filesystem produced by task 1 within its
own condition.

### Memory source

010B uses a deterministic hidden research oracle for memory records.
The model does not generate or edit memory.

This deliberately separates two questions:

1. whether structured persistent repository knowledge is useful;
2. whether a small model can reliably decide what should be persisted.

The second question is not tested in 010B.

### Memory semantics

A memory record contains:

- record ID
- kind
- claim
- evidence paths
- establishing task
- repository fingerprint metadata

010B does not perform freshness validation. Staleness is tested
separately in 010C.

Memory is evidence, not authority.

A memory record cannot:

- grant tool capability;
- expand workspace authority;
- authorize a write;
- suppress verification;
- override current repository or execution evidence.

Current evidence outranks persisted memory on conflict.

### Retrieval

010B uses no memory embedding index or vector database.

All bounded records established by task 1 are supplied to the related
task 2 in the structured-memory condition. Relevance is scored using a
hidden evaluator oracle.

### Measurements

For each task:

- behavioral success
- protocol validity
- model calls
- tool calls
- successful and failed tool calls
- discovery calls
- current context paths
- current context character count
- current evidence count
- memory records available
- memory records supplied
- memory evidence paths
- relevant and irrelevant supplied records
- memory character count
- total evidence character count
- changed files
- required-file recall
- allowed-file precision

For each sequence:

- repeated discovery operations between task 1 and task 2

### Interpretation constraints

A reduction in tool calls is not automatically an improvement.

An increase in context is an explicit cost.

Memory is not credited with behavioral improvement unless the hidden
behavior oracle passes.

A protocol-valid response is not behavioral success.

A repeated current-repository read may be legitimate revalidation rather
than waste.

Because this is a three-pair, single-run diagnostic using a small local
model at temperature 0, results are descriptive rather than estimates of
general performance.

No 010B result is used to claim that persistent memory should enter
production until the mechanism demonstrates measurable value.
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

## 010C — Stale-memory invalidation

### Question

When repository state changes after a memory record is established, can
deterministic provenance checking prevent stale repository claims from
reaching model context while preserving current repository evidence?

### Motivation

010B did not demonstrate behavioral value from structured memory.
However, any future persistent-memory mechanism still requires a
fail-safe freshness rule.

A repository claim that was correct when established may become
incorrect after its supporting files change. The model should not be
responsible for deciding whether such a record is still current.

### Hypothesis

A memory record can be invalidated deterministically by storing content
fingerprints for its evidence files when the record is established and
recomputing those fingerprints before retrieval.

If any supporting file differs from its recorded fingerprint, the record
is stale and must not reach model context.

### Conditions

For each fixture:

1. `no_freshness`
   - establish a valid record against V1
   - mutate its evidence to V2
   - retrieve without freshness validation
   - stale record is expected to reach memory context

2. `freshness`
   - establish the same record against V1
   - mutate its evidence to V2
   - validate provenance before retrieval
   - stale record is expected to be rejected

3. `freshness_with_current_evidence`
   - perform the same deterministic memory validation
   - reject the stale record
   - independently retrieve current repository evidence
   - current evidence must remain available

### Freshness rule

Each memory record stores SHA-256 content fingerprints for every
provenance file.

At retrieval time:

- missing evidence file -> stale
- changed evidence file -> stale
- unchanged evidence files -> fresh

The experiment deliberately uses exact content identity rather than
semantic similarity.

This is conservative. A harmless edit can invalidate a still-correct
claim. 010C measures safety behavior, not optimal invalidation
granularity.

### Measurements

- records available
- fresh records
- stale records
- stale records rejected
- stale records reaching memory context
- memory characters reaching context
- current repository evidence preserved

### Success criterion

For every fixture:

- `no_freshness` allows the deliberately stale record to reach context;
- `freshness` rejects it;
- `freshness_with_current_evidence` rejects it while preserving current
  repository evidence.

No model behavioral claim is required for 010C success.

### Interpretation constraints

Passing 010C does not demonstrate that persistent memory improves coding
performance.

It demonstrates only that the tested provenance mechanism can
deterministically prevent records whose supporting files changed from
being supplied as current memory.

Content-fingerprint invalidation may over-invalidate.

It does not detect semantic staleness caused by changes outside a
record's declared provenance.

Current repository evidence remains authoritative.
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