# Module 8 Conclusions: Planning and Subagents

## Research question

Does explicit task decomposition improve a small coding model's ability to
complete multi-step repository changes enough to justify the additional
inference and coordination cost?

## Scope

Module 8 investigated four related questions:

1. Can a 1.5B coding model produce useful structured plans?
2. Does deterministic repository structure improve those plans?
3. Does conditioning an implementer on an explicit plan improve implementation?
4. Can an independent reviewer catch incorrect implementations?

The experiments intentionally separated planning quality, implementation
quality, deterministic verification, and reviewer behavior rather than
evaluating them as one opaque agent pipeline.

All model experiments used Qwen2.5-Coder-1.5B-Instruct Q4_K_M at
temperature 0.0.

These experiments are small diagnostics, not broad benchmark results.

---

## 008A: Planning quality

008A compared:

- source-only planning;
- source plus deterministic repository structure.

After a protocol-only prompt correction, both conditions achieved valid
planning JSON for all eight tasks.

### Source only

- file precision: 1.000
- file recall: 0.8125
- symbol recall: 0.7917
- verification precision: 1.000
- verification recall: 0.8958
- unnecessary files: 0
- mean prompt characters: 1374.9

### Source plus structure

- file precision: 1.000
- file recall: 0.875
- symbol recall: 0.8542
- verification precision: 1.000
- verification recall: 0.8958
- unnecessary files: 0
- mean prompt characters: 1559.3

Repository structure therefore improved scope discovery slightly in this
diagnostic, particularly file and symbol recall.

However, qualitative inspection showed that plans could identify the right
files while still describing vague, incomplete, or incorrect semantic
operations.

The experiment therefore supports deterministic structure as grounding
assistance. It does not demonstrate improved semantic reasoning.

---

## 008B: Plan-conditioned implementation

008B replayed the frozen source-plus-structure plans from 008A.

This isolated the effect of plan conditioning:

- direct implementation received the task and visible repository;
- plan-conditioned implementation received the same information plus the
  frozen structured plan.

No repair loop or model-visible execution feedback was allowed.

### Direct implementation

- behavioral success: 1/8
- protocol valid: 7/8
- preflight valid: 6/8
- committed: 6/8
- required-file recall: 0.750
- required-file precision: 0.750
- unnecessary files: 0
- mean prompt characters: 1960.9
- total implementer model time: 119.71 seconds

### Plan-conditioned implementation

- behavioral success: 1/8
- protocol valid: 8/8
- preflight valid: 8/8
- committed: 8/8
- required-file recall: 0.9375
- required-file precision: 1.000
- unnecessary files: 0
- mean prompt characters: 2555.9
- total implementer model time: 123.48 seconds

Explicit planning substantially improved several mechanical properties:

- protocol adherence;
- applicability;
- commit rate;
- required-file coverage.

It did not improve behavioral success.

There was no task where plan conditioning converted a direct behavioral
failure into a behavioral success.

The planned condition also increased implementer prompt size by roughly
30%, before including the separate planner inference required by an
end-to-end planned system.

### Patch inspection

Manual inspection showed several distinct failure modes.

Correct scope did not imply correct implementation.

Examples included:

- semantic/reference corruption during a timeout rename;
- inverted authorization behavior;
- incomplete suspended-state presentation behavior;
- malformed YAML support;
- semantically vacuous edits despite correct file scope;
- incomplete propagation of a verbose execution option.

The plan-005 candidates also exposed an evaluation limitation.

Both passed the hidden runtime oracle, but both modified the visible
verification surface incorrectly. Runtime behavioral success therefore
must not be treated as complete task correctness.

The implementation evidence suggests that decomposition/scope discovery
and semantic implementation are separable bottlenecks.

---

## 008C: Independent review

008C evaluated an independent model reviewer over the frozen committed
patches from 008B.

Three conditions were tested:

1. patch only;
2. patch plus deterministic execution PASS/FAIL;
3. patch plus normalized execution evidence.

The frozen corpus contained 14 committed patches.

Two were syntactically invalid and had never reached hidden runtime
verification, leaving 12 runtime-verified candidates:

- 2 runtime PASS;
- 10 runtime FAIL.

### Patch only

- protocol valid: 14/14
- runtime true positive: 1
- runtime true negative: 6
- runtime false positive: 4
- runtime false negative: 1
- runtime-pass recall: 0.50
- runtime-fail recall: 0.60
- balanced accuracy: 0.55
- total model time: 134.17 seconds

The independent reviewer was not sufficiently reliable.

It falsely accepted several behaviorally incorrect patches, including
failures involving reference corruption, YAML handling, and multi-hop
propagation.

It also sometimes produced the correct verdict for an incorrect reason,
showing that verdict agreement alone can overstate semantic review quality.

Both syntax-invalid patches were rejected, but deterministic syntax
validation already detects this class of error without model inference.

### Execution signal

- protocol valid: 12/12
- runtime true positive: 2
- runtime true negative: 10
- runtime false positive: 0
- runtime false negative: 0
- runtime-pass recall: 1.00
- runtime-fail recall: 1.00
- balanced accuracy: 1.00
- total model time: 77.16 seconds

The reviewer perfectly reproduced the deterministic PASS/FAIL signal.

This does not demonstrate additional reviewer capability. Hewn already
possesses this signal before reviewer inference.

A deterministic accept/reject rule can perform the same mapping without an
additional model call.

### Execution evidence

- protocol valid: 11/12
- runtime true positive: 2
- runtime true negative: 9
- runtime false positive: 0
- runtime false negative: 0
- protocol failure: 1
- reported runtime-pass recall: 1.00
- reported runtime-fail recall: 0.90
- reported balanced accuracy: 0.95
- total model time: 123.75 seconds

The single protocol failure was caused by a repetitive response that was
truncated before the JSON object closed.

The model had already emitted a rejection verdict, so this was primarily a
protocol-generation failure rather than evidence of false semantic
acceptance.

Detailed normalized execution evidence did not improve verdict performance
over the simpler PASS/FAIL signal.

It instead added context, inference cost, and one protocol failure.

---

## Cross-experiment result

The experiments expose several distinct stages of coding-agent capability:

```text
relevant evidence
      ↓
correct scope
      ↓
useful decomposition
      ↓
applicable edit
      ↓
correct behavior
      ↓
reliable verification