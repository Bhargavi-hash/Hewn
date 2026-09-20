# Module 10 — Persistent Repository Intelligence

## Research question

Can persistent repository-specific knowledge reduce repeated discovery
work and improve coding-agent decisions across related tasks without
allowing stale, incorrect, or irrelevant memory to override current
repository evidence?

## Result

Persistent repository memory did not earn production integration on the
tested task distribution.

The experiments did establish two narrower results:

1. stateless repository evidence is repeatedly reconstructed across
   related tasks;
2. if historical repository memory is introduced later, provenance-based
   invalidation can deterministically prevent tested stale records from
   reaching memory context.

The experiments also suggest that persistent memory is most defensible
for historical information that cannot be reconstructed from the current
repository state.

## 010A — Repeated discovery baseline

Three related sequential task pairs were evaluated without persistent
memory.

Across the six tasks:

- behavioral success: 0/6;
- protocol-valid responses: 5/6;
- model-directed discovery calls: 0;
- reusable task-2 evidence repeated from task 1: 5/5;
- aggregate reusable-evidence overlap: 1.000.

All observed repetition occurred in automatic pre-model repository
retrieval rather than model-directed discovery.

The configuration pair also demonstrated that repeated context is not
equivalent to sufficient evidence: the repeated context included
`src/sample/client.py` and `tests/test_client.py`, while the actual
configuration definition lived in `src/sample/settings.py`.

Therefore 010A establishes repeated stateless retrieval in this
diagnostic, but not avoidable active rediscovery or a behavioral cost
caused by the absence of persistent memory.

## 010B — Structured memory

Each related task-2 request was evaluated under:

- stateless current repository retrieval;
- the same retrieval plus one bounded structured repository-memory
  record established from task 1.

Task-2 results:

- stateless behavioral success: 0/3;
- structured-memory behavioral success: 0/3;
- stateless protocol validity: 2/3;
- structured-memory protocol validity: 3/3;
- tool calls in either condition: 0;
- repeated discovery operations in either condition: 0.

The memory condition added between 424 and 489 characters per task.

The isolated protocol-validity difference is not evidence of memory
utility because behavioral success remained unchanged and the experiment
contains only three task pairs in one model run.

Structured memory therefore did not demonstrate behavioral improvement
or discovery reduction and introduced measurable context cost.

010B does not justify production persistent-memory integration.

## 010C — Stale-memory invalidation

A deterministic freshness mechanism stored SHA-256 fingerprints for each
memory record's declared provenance files.

After deliberately modifying one provenance file in each of three cases:

- without freshness validation, stale records reaching context: 3/3;
- with fingerprint validation, stale records rejected: 3/3;
- stale records reaching context after validation: 0/3;
- current repository evidence preserved: 3/3.

This establishes that exact provenance-file content fingerprints can
prevent the tested class of stale memory from reaching context.

The result is intentionally narrow.

Exact fingerprints can over-invalidate still-correct records after
irrelevant edits, and they cannot detect semantic invalidation caused by
changes outside a record's declared provenance.

## 010D — What is worth remembering?

Five constructed knowledge classes were tested for whether their expected
fact could be reconstructed from current repository state.

Results:

| Class | Reconstructible | Historical information required | Persistence candidate |
| --- | --- | --- | --- |
| Structural | yes | no | no |
| Architectural rationale | no | yes | yes |
| Operational configuration | yes | no | no |
| Historical failure | no | yes | yes |
| Decision rationale | no | yes | yes |

Structural and operational facts in these cases were recoverable from
current source or configuration.

Architectural rationale, historical failure information, and decision
rationale were not recoverable even though current source still exposed
evidence around the affected component.

This suggests an important distinction:

> Persistent memory is most defensible when it preserves information that
> disappears from the current repository state.

This experiment is a five-case taxonomy diagnostic. It does not estimate
how common or useful these knowledge classes are in real repositories.

Non-reconstructibility is necessary evidence for persistence in this
experiment, not sufficient evidence of usefulness.

## Cross-experiment interpretation

The original motivation for repository memory was that an agent working
repeatedly in the same repository should not continually rediscover the
same architecture, conventions, dependencies, failures, and decisions.

The experiments refine that idea.

### Current-state facts should usually be reconstructed

Hewn already has deterministic repository indexing and retrieval.

Persisting facts that are directly recoverable from current source risks
creating a second, stale representation of information the repository
already contains.

Examples include:

- symbol locations;
- imports;
- directly encoded dependencies;
- current test configuration;
- other mechanically recoverable structure.

These belong primarily in deterministic indexes and retrieval.

### Historical information is different

Some useful information disappears when repository state changes.

Examples include:

- why an architectural boundary exists;
- why an alternative implementation was rejected;
- a failure encountered in an earlier state;
- a repository-specific operational problem discovered through
  execution;
- a correction whose cause is no longer visible after the fix.

Current source may expose the resulting implementation without exposing
the historical reason behind it.

These are stronger candidates for persistence.

### Memory remains evidence, not authority

If Hewn later introduces persistent repository memory, the evidence
ordering should remain:

1. current deterministic repository evidence;
2. current execution evidence;
3. current retrieved source;
4. persisted repository memory;
5. unsupported model inference.

Memory must never grant capabilities, expand workspace authority,
authorize edits, suppress verification, or override conflicting current
evidence.

### Freshness should be deterministic where possible

010C supports provenance-based invalidation as a simple fail-safe
mechanism.

A future memory record should therefore carry inspectable provenance and
repository-state information rather than existing as an unsupported
natural-language assertion.

## Production decision

Do not add a general persistent-memory subsystem to Hewn yet.

010B did not demonstrate sufficient behavioral or discovery value to
justify the additional storage, retrieval, context, freshness, and
complexity costs.

Instead:

- continue reconstructing current structural facts from repository state;
- continue using deterministic retrieval for current evidence;
- preserve the memory record and freshness prototypes as research
  artifacts;
- revisit production persistence when Hewn has tasks that naturally
  generate valuable historical information across sessions.

The first production memory candidates should be historical rather than
structural:

1. architectural decisions and rationale;
2. verified historical failures and their corrections;
3. repository-specific operational discoveries that are not encoded in
   current configuration.

Even these candidates require behavioral evidence before production
promotion.

## Design principle

**Remember what the repository can no longer tell you. Recompute what it
still can.**

Persistent memory is evidence, not authority.

## Limitations

010A and 010B use three task pairs and a single local-model run at
temperature zero. They are diagnostic rather than estimates of general
coding-agent performance.

The local model achieved no behavioral successes in those experiments,
which limits the ability to measure downstream memory utility.

010C uses deliberately changed provenance files and exact content
fingerprints. It does not test semantic invalidation.

010D uses five hand-constructed taxonomy cases and does not measure the
frequency or real-world utility of each knowledge class.

No experiment in Module 10 establishes that persistent memory improves
Hewn's end-to-end coding performance.

## Module 10 conclusion

The broad hypothesis that persistent repository memory would improve
Hewn was not supported on the tested distribution.

However, the module identified a narrower design direction:

- do not duplicate mechanically reconstructible repository state;
- persist only information with genuine historical value;
- attach provenance to persisted claims;
- invalidate conservatively when supporting evidence changes;
- keep current repository and execution evidence above memory.

A future persistent-memory subsystem should be introduced only when a
measured workload demonstrates that historical repository knowledge
improves agent behavior enough to justify its cost.